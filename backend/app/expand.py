"""Expand supported OOXML click entrances into cumulative PPTX states.

Office Math fallback bitmaps are masked by paragraph when LibreOffice needs
them to preserve the original formula glyphs.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from posixpath import dirname, normpath
import re
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree
from PIL import Image

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS = {"p": P, "a": A, "a14": A14, "m": M, "r": R, "mc": MC}
REL_SLIDE = R + "/slide"
REL_LAYOUT = R + "/slideLayout"
REL_MASTER = R + "/slideMaster"
REL_IMAGE = R + "/image"
SLIDE_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"


@dataclass
class ExpansionReport:
    original_slides: int = 0
    output_pages: int = 0
    expanded_slides: int = 0
    fallback_slides: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Target:
    shape_id: str
    paragraphs: tuple[int, int] | None = None


class UnsupportedAnimationError(ValueError):
    def __init__(self, slide_number: int):
        self.slide_number = slide_number
        super().__init__(f"幻灯片 {slide_number} 的动画无法按原顺序准确展开")


def _xml(data: bytes):
    return etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))


def _bytes(element) -> bytes:
    return etree.tostring(element, encoding="UTF-8", xml_declaration=True, standalone=True)


def _slide_order(archive: ZipFile) -> list[str]:
    presentation = _xml(archive.read("ppt/presentation.xml"))
    rels = _xml(archive.read("ppt/_rels/presentation.xml.rels"))
    paths = {r.get("Id"): r.get("Target") for r in rels if r.get("Type") == REL_SLIDE}
    result = []
    for slide in presentation.xpath("./p:sldIdLst/p:sldId", namespaces=NS):
        rel_id = slide.get(f"{{{R}}}id")
        target = paths.get(rel_id)
        if not target:
            raise ValueError("幻灯片关系缺失")
        part = normpath("ppt/" + target.lstrip("/")) if not target.startswith("/") else target.lstrip("/")
        if not part.startswith("ppt/slides/") or part not in archive.namelist():
            raise ValueError("幻灯片路径无效")
        result.append(part)
    return result


def _related_part(archive: ZipFile, owner: str, rels, kind: str, directory: str):
    matches = [rel for rel in rels if rel.get("Type") == kind and not rel.get("TargetMode")]
    if len(matches) != 1:
        return None, None
    part = normpath(dirname(owner) + "/" + matches[0].get("Target", ""))
    if not part.startswith(directory + "/") or part not in archive.namelist():
        return None, None
    rel_path = f"{dirname(part)}/_rels/{Path(part).name}.rels"
    return _xml(archive.read(part)), _xml(archive.read(rel_path)) if rel_path in archive.namelist() else None


def _inherited_placeholder_styles(archive: ZipFile, slide_part: str, slide_rels) -> list:
    """Return layout then master, in PowerPoint's placeholder inheritance order."""
    if slide_rels is None:
        return []
    layout, layout_rels = _related_part(archive, slide_part, slide_rels, REL_LAYOUT, "ppt/slideLayouts")
    if layout is None:
        return []
    result = [layout]
    if layout_rels is not None:
        layout_rel = next((rel for rel in slide_rels if rel.get("Type") == REL_LAYOUT), None)
        if layout_rel is not None:
            layout_part = normpath(dirname(slide_part) + "/" + layout_rel.get("Target", ""))
            master, _ = _related_part(archive, layout_part, layout_rels, REL_MASTER, "ppt/slideMasters")
            if master is not None:
                result.append(master)
    return result


def _placeholder_key(shape):
    ph = shape.find(f"{{{P}}}nvSpPr/{{{P}}}nvPr/{{{P}}}ph")
    if ph is None:
        return None
    return ("idx", ph.get("idx")) if ph.get("idx") is not None else ("type", ph.get("type", "obj"))


def _matching_placeholder(style, shape):
    key = _placeholder_key(shape)
    candidates = [item for item in style.xpath('./p:cSld/p:spTree/p:sp', namespaces=NS)
                  if _placeholder_key(item) == key]
    if len(candidates) == 1:
        return candidates[0]
    ph = shape.find(f"{{{P}}}nvSpPr/{{{P}}}nvPr/{{{P}}}ph")
    kind = ph.get("type") if ph is not None else None
    if kind is None:
        return None
    candidates = [item for item in style.xpath('./p:cSld/p:spTree/p:sp', namespaces=NS)
                  if (candidate := item.find(f"{{{P}}}nvSpPr/{{{P}}}nvPr/{{{P}}}ph")) is not None
                  and candidate.get("type") == kind]
    return candidates[0] if len(candidates) == 1 else None


def _inherit_placeholder_autofit(state, styles: list) -> None:
    """Materialize inherited auto-fit so LibreOffice does not wrap titles."""
    if not styles:
        return
    for shape in state.xpath('./p:cSld/p:spTree/p:sp', namespaces=NS):
        key = _placeholder_key(shape)
        body = shape.find(f"{{{P}}}txBody/{{{A}}}bodyPr")
        if key is None or body is None or any(etree.QName(child).localname in
                                            {"normAutofit", "spAutoFit", "noAutofit"} for child in body):
            continue
        for style in styles:
            candidate = _matching_placeholder(style, shape)
            if candidate is None:
                continue
            inherited = candidate.find(f"{{{P}}}txBody/{{{A}}}bodyPr")
            if inherited is None:
                continue
            fit = next((child for child in inherited if etree.QName(child).localname in
                        {"normAutofit", "spAutoFit", "noAutofit"}), None)
            if fit is not None:
                warp = body.find(f"{{{A}}}prstTxWarp")
                body.insert(body.index(warp) + 1 if warp is not None else 0, deepcopy(fit))
                break


def _clicks(slide) -> tuple[list[list[Target]], bool]:
    timing = slide.find(f"{{{P}}}timing")
    if timing is None:
        return [], False
    # Static states cannot faithfully represent path, color, media, exit,
    # interactive, or repeating effects. Show the complete original slide.
    forbidden = {"animMotion", "animClr", "animRot", "animScale", "cmd", "audio", "video"}
    if any(etree.QName(el).localname in forbidden for el in timing.iter()):
        return [], True
    if timing.xpath('.//p:animEffect[@transition="out"] | .//p:set/p:to/p:strVal[@val="hidden"]', namespaces=NS):
        return [], True
    for node in timing.xpath(".//p:cTn", namespaces=NS):
        if node.get("presetClass") in {"exit", "emph", "path", "verb", "mediacall"}:
            return [], True
        if node.get("nodeType") == "interactiveSeq" or node.get("repeatCount"):
            return [], True
        inside_effect = node.get("nodeType") in {"clickEffect", "withEffect", "afterEffect"} or bool(
            node.xpath('ancestor::p:cTn[@nodeType="clickEffect" or @nodeType="withEffect" or @nodeType="afterEffect"]', namespaces=NS))
        if (node.get("presetClass") or node.get("nodeType") in {"withEffect", "afterEffect", "afterGroup"}) and not inside_effect:
            return [], True

    clicks: list[list[Target]] = []
    for node in timing.xpath('.//p:cTn[@nodeType="clickEffect" or @nodeType="withEffect" or @nodeType="afterEffect"]', namespaces=NS):
        # Entrance is the only state change we can flatten without inventing
        # intermediate geometry or appearance.
        if node.get("presetClass") != "entr" or node.xpath(
            'ancestor::p:cTn[@nodeType="clickEffect" or @nodeType="withEffect" or @nodeType="afterEffect"]', namespaces=NS):
            return [], True
        targets = []
        for shape in node.xpath(".//p:cBhvr/p:tgtEl/p:spTgt", namespaces=NS):
            sid = shape.get("spid")
            if not sid:
                return [], True
            pr = shape.find(f"{{{P}}}txEl/{{{P}}}pRg")
            if pr is not None:
                try:
                    span = (int(pr.get("st")), int(pr.get("end")))
                except (ValueError, TypeError):
                    return [], True
                targets.append(Target(sid, span))
            elif shape.find(f"{{{P}}}txEl") is not None:
                return [], True
            else:
                targets.append(Target(sid))
        if not targets:
            return [], True
        if node.get("nodeType") == "clickEffect":
            clicks.append([])
        elif not clicks:
            return [], True
        clicks[-1].extend(target for target in dict.fromkeys(targets) if target not in clicks[-1])
    if not clicks:
        return [], True
    # Overlapping effects on an object need more than a simple visibility state.
    flat = [target for group in clicks for target in group]
    if len(flat) != len(set(flat)) or len(clicks) > 60:
        return [], True
    for i, left in enumerate(flat):
        for right in flat[i + 1:]:
            if left.shape_id != right.shape_id:
                continue
            if left.paragraphs is None or right.paragraphs is None:
                return [], True
            if max(left.paragraphs[0], right.paragraphs[0]) <= min(left.paragraphs[1], right.paragraphs[1]):
                return [], True
    return clicks, False


def _hide_target(tree, target: Target):
    shapes = []
    for info in tree.xpath('.//p:cNvPr[@id=$shape_id]', namespaces=NS, shape_id=target.shape_id):
        shape = info.getparent().getparent()
        if shape is not tree and etree.QName(shape).namespace == P and etree.QName(shape).localname in {
            "sp", "pic", "graphicFrame", "cxnSp", "grpSp"
        }:
            shapes.append(shape)
    if not shapes:
        return False
    handled = False
    for shape in shapes:
        if target.paragraphs is None:
            parent = shape.getparent()
            if etree.QName(parent).localname in {"Choice", "Fallback"}:
                alternate = parent.getparent()
                if etree.QName(alternate).localname != "AlternateContent":
                    return False
                for variant in alternate:
                    if etree.QName(variant).localname not in {"Choice", "Fallback"}:
                        continue
                    for item in variant.xpath('./p:sp | ./p:pic | ./p:graphicFrame | ./p:cxnSp | ./p:grpSp', namespaces=NS):
                        ids = item.xpath('./*/p:cNvPr/@id', namespaces=NS)
                        if not ids or ids[0] != target.shape_id:
                            return False
                alternate.getparent().remove(alternate)
                return True
            parent.remove(shape)
            handled = True
            continue
        paragraphs = shape.findall(f"{{{P}}}txBody/{{{A}}}p")
        start, end = target.paragraphs
        if start < 0 or end < start or end >= len(paragraphs):
            continue
        for para in paragraphs[start:end + 1]:
            for text in para.iter(f"{{{A}}}t"):
                text.text = "\u00a0"
            for math in para.xpath('.//a14:m | .//m:oMathPara | .//m:oMath', namespaces=NS):
                if math.getparent() is not None:
                    math.getparent().remove(math)
            props = para.find(f"{{{A}}}pPr")
            if props is None:
                props = etree.Element(f"{{{A}}}pPr")
                para.insert(0, props)
            for bullet in list(props):
                if etree.QName(bullet).localname.startswith("bu"):
                    props.remove(bullet)
            props.insert(0, etree.Element(f"{{{A}}}buNone"))
        handled = True
    return handled


def _bounds(shape):
    transform = shape.find(f"{{{P}}}spPr/{{{A}}}xfrm")
    if transform is None:
        return None
    offset = transform.find(f"{{{A}}}off")
    extent = transform.find(f"{{{A}}}ext")
    if offset is None or extent is None:
        return None
    try:
        x, y = int(offset.get("x")), int(offset.get("y"))
        width, height = int(extent.get("cx")), int(extent.get("cy"))
    except (TypeError, ValueError):
        return None
    return (x, y, x + width, y + height) if width > 0 and height > 0 else None


def _hide_invisible_formula_artwork(tree) -> None:
    """Remove white-on-background fallback artwork when its backing is absent.

    PowerPoint can keep a white formula text box on a white slide, revealing
    it only when a colored rectangle appears beneath it. The transparent
    fallback bitmap leaves pale edges in LibreOffice even before that click.
    """
    shapes = list(tree)
    for position, overlay in enumerate(shapes):
        if overlay.tag != f"{{{MC}}}AlternateContent":
            continue
        choices = overlay.xpath('./mc:Choice/p:sp', namespaces=NS)
        if len(choices) != 1 or not choices[0].xpath('.//a14:m | .//m:oMath', namespaces=NS):
            continue
        if not overlay.xpath('./mc:Fallback//a:blip', namespaces=NS):
            continue
        inner = _bounds(choices[0])
        runs = choices[0].xpath('.//a:r[a:t] | .//m:r[m:t]', namespaces=NS)
        if inner is None or not runs or any(
            run.xpath('./a:rPr/a:solidFill/a:schemeClr/@val', namespaces=NS) != ['bg1'] for run in runs
        ):
            continue
        covered = False
        for backing in shapes[:position]:
            if backing.getparent() is not tree or backing.find(f"{{{P}}}spPr/{{{A}}}solidFill") is None:
                continue
            outer = _bounds(backing)
            if outer and outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]:
                covered = True
                break
        if not covered:
            tree.remove(overlay)


def _state(source, clicks: list[list[Target]], reached: int):
    slide = deepcopy(source)
    tree = slide.find(f"{{{P}}}cSld/{{{P}}}spTree")
    hidden = [target for group in clicks[reached:] for target in group]
    if tree is None:
        return None
    if any(not _hide_target(tree, target) for target in hidden):
        return None
    _hide_invisible_formula_artwork(tree)
    timing = slide.find(f"{{{P}}}timing")
    if timing is not None:
        slide.remove(timing)
    return _bytes(slide)


def _paragraph_bands(png: bytes, count: int) -> tuple[Image.Image, list[tuple[int, int]]]:
    """Locate distinct paragraph rows in an Office Math fallback PNG.

    Only a clear gap split is accepted. An ambiguous bitmap must not produce
    a plausible looking PDF with content in the wrong animation state.
    """
    with Image.open(BytesIO(png)) as source:
        if source.format != "PNG" or "transparency" not in source.info and "A" not in source.getbands():
            raise ValueError("公式备援图片缺少透明通道")
        if source.width * source.height > 20_000_000:
            raise ValueError("公式备援图片超过安全尺寸")
        image = source.convert("RGBA")
    alpha = image.getchannel("A")
    active = []
    for y in range(image.height):
        row = alpha.crop((0, y, image.width, y + 1)).point(lambda value: 255 if value > 16 else 0)
        active.append(row.getbbox() is not None)
    spans = []
    start = None
    for y, visible in enumerate(active + [False]):
        if visible and start is None:
            start = y
        elif not visible and start is not None:
            if spans and start - spans[-1][1] <= 4:
                spans[-1] = (spans[-1][0], y - 1)
            else:
                spans.append((start, y - 1))
            start = None
    if count < 1 or len(spans) < count or len(spans) > count * 4:
        raise ValueError("公式备援图片的段落数量不匹配")
    if spans and min(end - begin + 1 for begin, end in spans) * 2 < max(end - begin + 1 for begin, end in spans):
        raise ValueError("公式备援图片的文字行边界不明确")
    gaps = [spans[i + 1][0] - spans[i][1] - 1 for i in range(len(spans) - 1)]
    wraps = len(spans) - count
    wrapped = set(sorted(range(len(gaps)), key=lambda i: gaps[i])[:wraps])
    boundaries = [i for i in range(len(gaps)) if i not in wrapped]
    if wrapped and boundaries and max(gaps[i] for i in wrapped) * 4 >= min(gaps[i] for i in boundaries) * 3:
        raise ValueError("公式备援图片的段落间距不明确")
    groups = []
    first = 0
    for boundary in boundaries:
        groups.append((spans[first][0], spans[boundary][1]))
        first = boundary + 1
    groups.append((spans[first][0], spans[-1][1]))
    if len(groups) != count:
        raise ValueError("公式备援图片无法对应动画段落")
    return image, groups


def _mask_formula_fallbacks(state, rels, original: ZipFile, part: str,
                            hidden: list[Target], page_index: int) -> list[tuple[str, bytes]]:
    grouped: dict[str, set[int]] = {}
    for target in hidden:
        if target.paragraphs is not None:
            grouped.setdefault(target.shape_id, set()).update(range(target.paragraphs[0], target.paragraphs[1] + 1))
    media = []
    for shape_id, concealed in grouped.items():
        choices = state.xpath('.//mc:AlternateContent/mc:Choice/p:sp[p:nvSpPr/p:cNvPr[@id=$shape_id]]',
                              namespaces=NS, shape_id=shape_id)
        if not choices:
            continue
        if len(choices) != 1:
            raise ValueError("公式备援形状不明确")
        choice = choices[0]
        alternate = choice.getparent().getparent()
        blips = alternate.xpath('./mc:Fallback//a:blip', namespaces=NS)
        paragraphs = choice.findall(f"{{{P}}}txBody/{{{A}}}p")
        if len(blips) != 1 or not paragraphs:
            raise ValueError("公式备援图片缺失")
        blip = blips[0]
        old_id = blip.get(f"{{{R}}}embed")
        relation = next((rel for rel in rels if rel.get("Id") == old_id and rel.get("Type") == REL_IMAGE), None)
        if relation is None or relation.get("TargetMode"):
            raise ValueError("公式备援图片关系缺失")
        image_part = normpath(dirname(part) + "/" + relation.get("Target", ""))
        if not image_part.startswith("ppt/media/") or image_part not in original.namelist():
            raise ValueError("公式备援图片路径无效")
        image, groups = _paragraph_bands(original.read(image_part), len(paragraphs))
        alpha = image.getchannel("A")
        for index in concealed:
            if index >= len(groups):
                raise ValueError("公式备援图片段落无效")
            top, bottom = groups[index]
            alpha.paste(0, (0, top, image.width, bottom + 1))
        image.putalpha(alpha)
        payload = BytesIO()
        image.save(payload, format="PNG", optimize=True)
        new_id = f"rIdAnimImage{page_index}_{len(media) + 1}"
        if any(rel.get("Id") == new_id for rel in rels):
            raise ValueError("公式备援图片关系冲突")
        media_name = f"animPdf{page_index}_{len(media) + 1}.png"
        etree.SubElement(rels, f"{{{PKG}}}Relationship", Id=new_id, Type=REL_IMAGE,
                         Target=f"../media/{media_name}")
        blip.set(f"{{{R}}}embed", new_id)
        media.append((f"ppt/media/{media_name}", payload.getvalue()))
    return media


def _table_fallback_picture(choice, fallback):
    """Use a table's original full-table bitmap once, not once per cell."""
    if choice.tag != f"{{{P}}}graphicFrame" or not choice.xpath('.//a:tbl', namespaces=NS):
        return None
    if fallback.tag != f"{{{P}}}graphicFrame":
        raise ValueError("表格公式备援格式不受支持")
    embeds = fallback.xpath('.//a:blip/@r:embed', namespaces=NS)
    if len(embeds) < 2 or len(set(embeds)) != 1:
        raise ValueError("表格公式备援不是完整图片")
    identity = choice.find(f"{{{P}}}nvGraphicFramePr/{{{P}}}cNvPr")
    transform = choice.find(f"{{{P}}}xfrm")
    if identity is None or transform is None or transform.find(f"{{{A}}}off") is None or transform.find(f"{{{A}}}ext") is None:
        raise ValueError("表格公式备援缺少位置")
    picture = etree.Element(f"{{{P}}}pic")
    metadata = etree.SubElement(picture, f"{{{P}}}nvPicPr")
    metadata.append(deepcopy(identity))
    locks = etree.SubElement(metadata, f"{{{P}}}cNvPicPr")
    etree.SubElement(locks, f"{{{A}}}picLocks", noChangeAspect="1")
    etree.SubElement(metadata, f"{{{P}}}nvPr")
    fill = etree.SubElement(picture, f"{{{P}}}blipFill")
    etree.SubElement(fill, f"{{{A}}}blip", attrib={f"{{{R}}}embed": embeds[0]})
    stretch = etree.SubElement(fill, f"{{{A}}}stretch")
    etree.SubElement(stretch, f"{{{A}}}fillRect")
    props = etree.SubElement(picture, f"{{{P}}}spPr")
    image_transform = etree.SubElement(props, f"{{{A}}}xfrm")
    image_transform.append(deepcopy(transform.find(f"{{{A}}}off")))
    image_transform.append(deepcopy(transform.find(f"{{{A}}}ext")))
    geometry = etree.SubElement(props, f"{{{A}}}prstGeom", prst="rect")
    etree.SubElement(geometry, f"{{{A}}}avLst")
    return picture


def _normalize_symbol_fonts(state) -> None:
    """Replace a known Wingdings private-use arrow with its Unicode form."""
    for run in state.xpath('.//a:r[a:rPr/a:latin[@typeface="Wingdings"] or '
                           'a:rPr/a:sym[@typeface="Wingdings"]]', namespaces=NS):
        text = run.find(f"{{{A}}}t")
        if text is None or not text.text or "\uf0e0" not in text.text:
            continue
        text.text = text.text.replace("\uf0e0", "\u2794")
        props = run.find(f"{{{A}}}rPr")
        symbol = props.find(f"{{{A}}}sym")
        if symbol is not None and symbol.get("typeface") == "Wingdings":
            symbol.tag = f"{{{A}}}latin"
            symbol.attrib.clear()
            symbol.set("typeface", "Noto Sans Symbols2")
        for font in (props.find(f"{{{A}}}{kind}") for kind in ("latin", "ea", "cs")):
            if font is not None:
                font.set("typeface", "Noto Sans Symbols2")


def _highlight_band(image: Image.Image) -> tuple[int, int] | None:
    """Find both edges of the original yellow bottom-row highlight."""
    rgb = image.convert("RGB")
    if rgb.width * rgb.height > 20_000_000:
        return None
    start = int(rgb.height * .65)
    sample = [int(rgb.width * fraction) for fraction in (.25, .5, .75)]
    active = []
    for y in range(start, rgb.height):
        yellow = sum(220 <= (pixel := rgb.getpixel((x, y)))[0] <= 255 and
                     185 <= pixel[1] <= 245 and 130 <= pixel[2] <= 210
                     for x in sample)
        active.append(yellow >= 2)
    runs = []
    first = None
    for y, present in list(zip(range(start, rgb.height), active)) + [(rgb.height, False)]:
        if present and first is None:
            first = y
        elif not present and first is not None:
            if y - first >= 5:
                runs.append((first, y))
            first = None
    if not runs:
        return None
    merged = [runs[0]]
    for begin, end in runs[1:]:
        if begin - merged[-1][1] <= 6:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((begin, end))
    return merged[-1]


def _align_table_highlights(state, rels, original: ZipFile, part: str, snapshots: list[tuple[str, str]]) -> None:
    """Keep an outlined 'Ours' row aligned with its full-table bitmap."""
    if rels is None:
        return
    tree = state.find(f"{{{P}}}cSld/{{{P}}}spTree")
    if tree is None:
        return
    for shape_id, image_id in snapshots:
        picture = state.xpath('.//p:pic[p:nvPicPr/p:cNvPr[@id=$shape_id]]',
                              namespaces=NS, shape_id=shape_id)
        relation = next((rel for rel in rels if rel.get("Id") == image_id and rel.get("Type") == REL_IMAGE), None)
        if len(picture) != 1 or relation is None or relation.get("TargetMode"):
            continue
        image_part = normpath(dirname(part) + "/" + relation.get("Target", ""))
        if not image_part.startswith("ppt/media/") or image_part not in original.namelist():
            continue
        with Image.open(BytesIO(original.read(image_part))) as image:
            band = _highlight_band(image)
            height = image.height
        if band is None:
            continue
        frame = picture[0].find(f"{{{P}}}spPr/{{{A}}}xfrm")
        off = frame.find(f"{{{A}}}off")
        ext = frame.find(f"{{{A}}}ext")
        if off is None or ext is None:
            continue
        x, y, width, frame_height = (int(off.get("x")), int(off.get("y")),
                                      int(ext.get("cx")), int(ext.get("cy")))
        top_pixel, bottom_pixel = band
        desired_top = y + round(frame_height * max(0, top_pixel - 1) / height)
        desired_bottom = y + round(frame_height * min(height, bottom_pixel + 1) / height)
        for sibling in tree:
            if sibling.tag != f"{{{P}}}sp" or sibling.find(f"{{{P}}}spPr/{{{A}}}noFill") is None:
                continue
            props = sibling.find(f"{{{P}}}spPr")
            if props.find(f"{{{A}}}ln") is None:
                continue
            transform = props.find(f"{{{A}}}xfrm")
            if transform is None:
                continue
            border_off = transform.find(f"{{{A}}}off")
            border_ext = transform.find(f"{{{A}}}ext")
            if border_off is None or border_ext is None:
                continue
            bx, by = int(border_off.get("x")), int(border_off.get("y"))
            bw, bh = int(border_ext.get("cx")), int(border_ext.get("cy"))
            if abs(bx - x) > width * .01 or abs(bw - width) > width * .01:
                continue
            if abs((by + bh) - (y + frame_height)) > frame_height * .04:
                continue
            if abs(by - desired_top) > frame_height * .12:
                continue
            border_off.set("y", str(desired_top))
            border_ext.set("cy", str(desired_bottom - desired_top))


def _prefer_formula_fallbacks(source, state):
    """Make formula rendering independent of LibreOffice's Choice selection."""
    math = source.xpath('.//a14:m | .//m:oMathPara | .//m:oMath', namespaces=NS)
    if not math:
        return
    originals = source.xpath('.//mc:AlternateContent[mc:Choice[.//a14:m or .//m:oMathPara or .//m:oMath]]',
                             namespaces=NS)
    if not originals or any(not node.xpath('ancestor::mc:Choice', namespaces=NS) for node in math):
        raise ValueError("公式缺少可用的原始图片")
    ids = set()
    for alternate in originals:
        identifiers = alternate.xpath('./mc:Choice/*/*/p:cNvPr/@id', namespaces=NS)
        fallback = alternate.find(f"{{{MC}}}Fallback")
        if len(identifiers) != 1 or identifiers[0] in ids or fallback is None or len(fallback) != 1:
            raise ValueError("公式备援形状不明确")
        if not fallback.xpath('.//a:blip', namespaces=NS):
            raise ValueError("公式缺少可用的原始图片")
        ids.add(identifiers[0])
    snapshots = []
    for alternate in state.xpath('.//mc:AlternateContent', namespaces=NS):
        identifiers = alternate.xpath('./mc:Choice/*/*/p:cNvPr/@id', namespaces=NS)
        if not identifiers or identifiers[0] not in ids:
            continue
        fallback = alternate.find(f"{{{MC}}}Fallback")
        if fallback is None or len(fallback) != 1:
            raise ValueError("公式备援形状不明确")
        choice = alternate.find(f"{{{MC}}}Choice")
        if choice is None or len(choice) != 1:
            raise ValueError("公式备援形状不明确")
        picture = _table_fallback_picture(choice[0], fallback[0])
        if picture is not None:
            snapshots.append((identifiers[0], picture.xpath('./p:blipFill/a:blip/@r:embed', namespaces=NS)[0]))
        alternate.getparent().replace(alternate, picture if picture is not None else deepcopy(fallback[0]))
    return snapshots


def expand_pptx(source: Path, destination: Path, max_pages: int = 3000) -> ExpansionReport:
    report = ExpansionReport()
    with ZipFile(source) as original:
        slide_paths = _slide_order(original)
        report.original_slides = len(slide_paths)
        if not slide_paths:
            raise ValueError("演示文稿没有幻灯片")
        existing_parts = set(original.namelist())
        numbered_parts = [int(match.group(1)) for part in existing_parts
                          if (match := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", part))]
        highest_slide_number = max(numbered_parts, default=0)
        presentation = _xml(original.read("ppt/presentation.xml"))
        pres_rels = _xml(original.read("ppt/_rels/presentation.xml.rels"))
        types = _xml(original.read("[Content_Types].xml"))
        ids = presentation.find(f"{{{P}}}sldIdLst")
        if ids is None:
            raise ValueError("演示文稿没有幻灯片目录")
        highest_id = max((int(item.get("id")) for item in ids), default=255)
        for item in list(ids):
            ids.remove(item)
        used_rels = {item.get("Id") for item in pres_rels}
        replaced = {"ppt/presentation.xml", "ppt/_rels/presentation.xml.rels", "[Content_Types].xml"}
        with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=3, allowZip64=True) as output:
            for info in original.infolist():
                if info.filename in replaced:
                    continue
                if info.is_dir():
                    output.writestr(info, b"")
                else:
                    with original.open(info) as reader, output.open(info.filename, "w", force_zip64=True) as writer:
                        for block in iter(lambda: reader.read(1024 * 1024), b""):
                            writer.write(block)
            for number, part in enumerate(slide_paths, 1):
                slide = _xml(original.read(part))
                clicks, fallback = _clicks(slide)
                first = None if fallback else _state(slide, clicks, 0)
                if first is None:
                    raise UnsupportedAnimationError(number)
                if clicks:
                    report.expanded_slides += 1
                count = len(clicks) + 1
                if report.output_pages + count > max_pages:
                    raise ValueError(f"展开后超过 {max_pages} 页的安全上限")
                rel_path = f"{dirname(part)}/_rels/{Path(part).name}.rels"
                rel_data = original.read(rel_path) if rel_path in existing_parts else None
                styles = _inherited_placeholder_styles(original, part, _xml(rel_data) if rel_data else None)
                for reached in range(count):
                    index = report.output_pages + 1
                    slide_name = f"slide{highest_slide_number + index}.xml"
                    name = f"ppt/slides/{slide_name}"
                    new_rel_path = f"ppt/slides/_rels/{slide_name}.rels"
                    rel_id = f"rIdAnimPdf{index}"
                    if name in existing_parts or new_rel_path in existing_parts or rel_id in used_rels:
                        raise ValueError("幻灯片内部名称冲突")
                    data = first if reached == 0 else _state(slide, clicks, reached)
                    if data is None:
                        raise UnsupportedAnimationError(number)
                    state = _xml(data)
                    _inherit_placeholder_autofit(state, styles)
                    _normalize_symbol_fonts(state)
                    rels = _xml(rel_data) if rel_data else None
                    hidden = [target for group in clicks[reached:] for target in group]
                    try:
                        media = _mask_formula_fallbacks(state, rels, original, part, hidden, index) if rels is not None else []
                        snapshots = _prefer_formula_fallbacks(slide, state)
                        _align_table_highlights(state, rels, original, part, snapshots or [])
                    except ValueError as exc:
                        raise UnsupportedAnimationError(number) from exc
                    if any(media_name in existing_parts for media_name, _ in media):
                        raise ValueError("公式备援图片名称冲突")
                    output.writestr(name, _bytes(state))
                    if rels is not None:
                        output.writestr(new_rel_path, _bytes(rels))
                    for media_name, payload in media:
                        output.writestr(media_name, payload)
                    etree.SubElement(pres_rels, f"{{{PKG}}}Relationship", Id=rel_id, Type=REL_SLIDE, Target=f"slides/{Path(name).name}")
                    etree.SubElement(ids, f"{{{P}}}sldId", id=str(highest_id + index), attrib={f"{{{R}}}id": rel_id})
                    etree.SubElement(types, f"{{{CT}}}Override", PartName="/" + name, ContentType=SLIDE_TYPE)
                    used_rels.add(rel_id)
                    report.output_pages += 1
            output.writestr(original.getinfo("ppt/presentation.xml"), _bytes(presentation))
            output.writestr(original.getinfo("ppt/_rels/presentation.xml.rels"), _bytes(pres_rels))
            output.writestr(original.getinfo("[Content_Types].xml"), _bytes(types))
    return report
