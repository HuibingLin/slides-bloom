import type { Metadata } from "next";
import { languageNames, Locale, translate } from "../i18n";
import { authorName, authorUrl, repositoryUrl, siteUrl } from "../site";

const paths: Record<Locale, string> = {
  en: "/ppt-animation-to-pdf",
  "zh-CN": "/zh-cn/ppt-animation-to-pdf",
  "zh-TW": "/zh-tw/ppt-animation-to-pdf",
};

const copy = {
  en: {
    title: "PPT Animation to PDF: Keep Every Click as a Page | Slides Bloom",
    description: "Download a real animated PPTX and its four-page PDF. See the starting slide and each click in order, then convert your own PowerPoint with Slides Bloom.",
    back: "Back to converter",
    eyebrow: "Illustrated guide · PPTX to PDF",
    heading: "PPT Animation to PDF: keep every click as a page",
    intro: "A normal PDF export gives you static slides. If your PowerPoint builds a list one click at a time, the reader may lose that sequence. Slides Bloom expands supported click-triggered entrance animations into separate, cumulative PDF pages.",
    tryTool: "Convert your PPTX",
    figureAlt: "One animated PPTX slide expands into four PDF pages: the starting state, then the states after clicks one, two, and three; each page keeps earlier flowers.",
    figureCaption: "Illustration of the output sequence. This is a diagram, not a converted sample file.",
    exampleHeading: "One slide, three clicks, four PDF pages",
    exampleIntro: "Imagine a slide with a title and three points set to appear on separate clicks. The PDF records the visible state after each step:",
    demoHeading: "Inspect a real conversion",
    demoIntro: "The downloadable PPTX has one slide and three separate click entrances. Slides Bloom expanded it into four pages, then LibreOffice rendered the PDF. Compare the files and the page previews below.",
    demoPptx: "Download sample PPTX",
    demoPdf: "Open converted PDF",
    demoNote: "This example uses simple text entrances. Other effects and fonts can render differently, so check the preview for your own presentation.",
    states: [
      ["Page 1 · Before clicks", "The title and any content already visible on the slide."],
      ["Page 2 · Click 1", "The starting slide plus point 1."],
      ["Page 3 · Click 2", "The starting slide plus points 1 and 2."],
      ["Page 4 · Click 3", "The starting slide plus points 1, 2, and 3."],
    ],
    differenceHeading: "How is this different from a regular PPT to PDF converter?",
    regularTitle: "Regular PDF export",
    regularBody: "PDF pages are static. A usual export produces one page for each original slide, so the click-by-click build is not available to the reader.",
    bloomTitle: "Slides Bloom",
    bloomBody: "Supported entrance clicks are unfolded before rendering. The resulting PDF has the starting state and each later state in animation order, within one file.",
    howHeading: "Convert your animated PowerPoint",
    howSteps: [
      ["Upload a .pptx", "Use the converter on the home page. The current limit is 20 MB; remove large embedded videos first."],
      ["Wait for conversion", "Slides Bloom reads supported click groups, creates a sequence of slide states, and renders them with LibreOffice."],
      ["Preview every page", "Check the order, formulas, special symbols, fonts, and layout in the browser before downloading the PDF."],
    ],
    limitsHeading: "What to check before sharing",
    limits: [
      "The PDF does not play animations. It contains static snapshots of the supported steps.",
      "Complex effects such as motion paths, exits, media, or interactive sequences cannot always be unfolded. Some slides may be exported fully visible; other unsupported cases can stop conversion and identify the slide.",
      "Rendering depends on the fonts and Office features available to LibreOffice. Embedded formula artwork is used when available, but exact visual fidelity cannot be guaranteed for every file.",
    ],
    closing: "Have a presentation with click-to-reveal content? Upload the PPTX, inspect the preview, and download the expanded PDF.",
  },
  "zh-CN": {
    title: "PPT 动画转 PDF：每次点击生成一页 | Slides Bloom",
    description: "通过图解了解如何将一张带点击动画的 PPT 幻灯片转成起始页和逐次累积的 PDF 页面，并用 Slides Bloom 转换自己的 PPTX。",
    back: "返回转换工具",
    eyebrow: "图解教程 · PPTX 转 PDF",
    heading: "PPT 动画转 PDF：保留每次点击后的页面",
    intro: "普通 PDF 导出只有静态幻灯片。如果 PowerPoint 中的要点逐次点击才出现，阅读者就看不到这个顺序。Slides Bloom 会把受支持的点击进入动画展开成独立且逐步累积的 PDF 页面。",
    tryTool: "转换我的 PPTX",
    figureAlt: "一张有三次点击动画的 PPTX 幻灯片变成四页 PDF：起始页，以及第 1、2、3 次点击后的页面；先前出现的花会保留。",
    figureCaption: "输出顺序示意图；这是一张图解，不是真实转换的示例文件。",
    exampleHeading: "一张幻灯片，三次点击，四页 PDF",
    exampleIntro: "假设一张幻灯片有标题，另有三个要点分别在点击后出现。PDF 会按以下顺序记录画面：",
    demoHeading: "查看真实转换结果",
    demoIntro: "可下载的 PPTX 包含一张幻灯片和三个独立的点击进入动画。Slides Bloom 将它展开成四页，再由 LibreOffice 渲染为 PDF。可以下载源文件并对照下面的页面预览。示例幻灯片使用英文文字。",
    demoPptx: "下载示例 PPTX",
    demoPdf: "打开转换后的 PDF",
    demoNote: "此示例使用简单的文字进入动画。其他动画效果和字体可能呈现不同结果，请检查自己文件的预览。",
    states: [
      ["第 1 页 · 点击前", "标题和原本就显示的内容。"],
      ["第 2 页 · 第 1 次点击", "起始画面加上第 1 个要点。"],
      ["第 3 页 · 第 2 次点击", "起始画面加上第 1、2 个要点。"],
      ["第 4 页 · 第 3 次点击", "起始画面加上第 1、2、3 个要点。"],
    ],
    differenceHeading: "与普通 PPT 转 PDF 有什么区别？",
    regularTitle: "普通 PDF 导出",
    regularBody: "PDF 页面本身是静态的。普通导出通常一张原始幻灯片对应一页，阅读者看不到逐次点击的展开过程。",
    bloomTitle: "Slides Bloom",
    bloomBody: "先展开受支持的点击进入动画，再渲染 PDF。一个文件中包含起始画面和按动画顺序生成的后续画面。",
    howHeading: "如何转换带动画的 PowerPoint",
    howSteps: [
      ["上传 .pptx", "在首页使用转换工具。目前文件上限为 20 MB，建议先移除较大的内嵌视频。"],
      ["等待转换", "Slides Bloom 读取受支持的点击分组，生成连续的画面，再交给 LibreOffice 渲染。"],
      ["逐页预览", "下载 PDF 前，在浏览器检查顺序、公式、特殊符号、字体和排版。"],
    ],
    limitsHeading: "分享前需要检查什么",
    limits: [
      "PDF 不会播放原始动画；它包含受支持步骤对应的静态页面。",
      "运动路径、退出动画、媒体或交互序列等复杂效果不一定能展开。部分幻灯片可能以全部内容可见的形式导出；其他不支持的情况可能中止转换并指出幻灯片。",
      "渲染结果取决于 LibreOffice 可用的字体和 Office 功能。有内嵌公式图像时会尽量使用，但无法保证每个文件都完全一致。",
    ],
    closing: "如果你的 PPT 有逐次点击出现的内容，可以上传 PPTX、检查预览，再下载展开后的 PDF。",
  },
  "zh-TW": {
    title: "PPT 動畫轉 PDF：每次點擊產生一頁 | Slides Bloom",
    description: "透過圖解了解如何將一張含點擊動畫的 PPT 投影片轉成起始頁與逐步累積的 PDF 頁面，並用 Slides Bloom 轉換自己的 PPTX。",
    back: "返回轉換工具",
    eyebrow: "圖解教學 · PPTX 轉 PDF",
    heading: "PPT 動畫轉 PDF：保留每次點擊後的頁面",
    intro: "一般 PDF 匯出只有靜態投影片。如果 PowerPoint 的重點要逐次點擊才出現，讀者就看不到這個順序。Slides Bloom 會把支援的點擊進入動畫展開成獨立且逐步累積的 PDF 頁面。",
    tryTool: "轉換我的 PPTX",
    figureAlt: "一張有三次點擊動畫的 PPTX 投影片變成四頁 PDF：起始頁，以及第 1、2、3 次點擊後的頁面；先前出現的花會保留。",
    figureCaption: "輸出順序示意圖；這是圖解，不是真實轉換的範例檔案。",
    exampleHeading: "一張投影片，三次點擊，四頁 PDF",
    exampleIntro: "假設一張投影片有標題，另有三個重點分別在點擊後出現。PDF 會依下列順序記錄畫面：",
    demoHeading: "查看實際轉換結果",
    demoIntro: "可下載的 PPTX 包含一張投影片和三個獨立的點擊進入動畫。Slides Bloom 將它展開成四頁，再由 LibreOffice 渲染為 PDF。你可以下載來源檔並對照下方的頁面預覽。範例投影片使用英文文字。",
    demoPptx: "下載範例 PPTX",
    demoPdf: "開啟轉換後的 PDF",
    demoNote: "此範例使用簡單的文字進入動畫。其他動畫效果及字型可能呈現不同結果，請檢查自己檔案的預覽。",
    states: [
      ["第 1 頁 · 點擊前", "標題和原本就顯示的內容。"],
      ["第 2 頁 · 第 1 次點擊", "起始畫面加上第 1 個重點。"],
      ["第 3 頁 · 第 2 次點擊", "起始畫面加上第 1、2 個重點。"],
      ["第 4 頁 · 第 3 次點擊", "起始畫面加上第 1、2、3 個重點。"],
    ],
    differenceHeading: "和一般 PPT 轉 PDF 有什麼不同？",
    regularTitle: "一般 PDF 匯出",
    regularBody: "PDF 頁面本身是靜態的。一般匯出通常一張原始投影片對應一頁，讀者看不到逐次點擊的展開過程。",
    bloomTitle: "Slides Bloom",
    bloomBody: "先展開支援的點擊進入動畫，再渲染 PDF。同一檔案中包含起始畫面及依動畫順序產生的後續畫面。",
    howHeading: "如何轉換含動畫的 PowerPoint",
    howSteps: [
      ["上傳 .pptx", "在首頁使用轉換工具。目前檔案上限為 20 MB，建議先移除較大的內嵌影片。"],
      ["等待轉換", "Slides Bloom 讀取支援的點擊群組，產生連續畫面，再交由 LibreOffice 渲染。"],
      ["逐頁預覽", "下載 PDF 前，在瀏覽器檢查順序、公式、特殊符號、字型和排版。"],
    ],
    limitsHeading: "分享前需要檢查什麼",
    limits: [
      "PDF 不會播放原始動畫；它包含支援步驟對應的靜態頁面。",
      "移動路徑、退出動畫、媒體或互動序列等複雜效果不一定能展開。部分投影片可能以全部內容可見的形式匯出；其他不支援的情況可能中止轉換並指出投影片。",
      "渲染結果取決於 LibreOffice 可用的字型與 Office 功能。有內嵌公式圖像時會盡量使用，但無法保證每個檔案都完全一致。",
    ],
    closing: "如果你的 PPT 有逐次點擊出現的內容，可以上傳 PPTX、檢查預覽，再下載展開後的 PDF。",
  },
} as const;

export function guideMetadata(locale: Locale): Metadata {
  const content = copy[locale];
  const url = `${siteUrl}${paths[locale]}`;
  return {
    title: content.title,
    description: content.description,
    alternates: {
      canonical: url,
      languages: {
        en: `${siteUrl}${paths.en}`,
        "zh-CN": `${siteUrl}${paths["zh-CN"]}`,
        "zh-TW": `${siteUrl}${paths["zh-TW"]}`,
        "x-default": `${siteUrl}${paths.en}`,
      },
    },
    robots: { index: true, follow: true },
    openGraph: {
      type: "article", url, siteName: "Slides Bloom", title: content.title,
      description: content.description,
      locale: locale === "en" ? "en_US" : locale === "zh-CN" ? "zh_CN" : "zh_TW",
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Slides Bloom PPT animation to PDF converter" }],
    },
  };
}

export default function GuideContent({ locale }: { locale: Locale }) {
  const content = copy[locale];
  return <div className="guide-page" lang={locale}>
    <header className="guide-topbar">
      <a className="guide-brand" href="/" aria-label="Slides Bloom home"><span className="brand-mark"><span>1</span><span>2</span><span>3</span></span>Slides Bloom</a>
      <nav aria-label="Languages" className="guide-languages">
        {(["en", "zh-TW", "zh-CN"] as const).map(language => <a key={language} href={paths[language]} lang={language} aria-current={locale === language ? "page" : undefined}>{languageNames[language]}</a>)}
      </nav>
    </header>
    <main className="guide-main">
      <a className="guide-back" href="/">← {content.back}</a>
      <div className="guide-eyebrow">{content.eyebrow}</div>
      <h1>{content.heading}</h1>
      <p className="guide-lead">{content.intro}</p>
      <a className="guide-cta" href="/#headline">{content.tryTool} <span aria-hidden="true">→</span></a>

      <figure className="guide-figure">
        <img src="/animation-steps.svg" width="1120" height="440" alt={content.figureAlt}/>
        <figcaption>{content.figureCaption}</figcaption>
      </figure>

      <section aria-labelledby="example-heading">
        <h2 id="example-heading">{content.exampleHeading}</h2>
        <p>{content.exampleIntro}</p>
        <ol className="guide-states">{content.states.map(([title, body]) => <li key={title}><strong>{title}</strong><span>{body}</span></li>)}</ol>
      </section>

      <section className="guide-demo" aria-labelledby="demo-heading">
        <h2 id="demo-heading">{content.demoHeading}</h2>
        <p>{content.demoIntro}</p>
        <div className="guide-demo-actions">
          <a href="/examples/animation-steps-demo.pptx" download>{content.demoPptx}</a>
          <a href="/examples/animation-steps-demo.pdf" target="_blank" rel="noopener noreferrer">{content.demoPdf}</a>
        </div>
        <div className="guide-demo-pages">
          {content.states.map(([title, body], index) => <figure key={title}>
            <img src={`/examples/page-${index + 1}.png`} width="1467" height="825" loading="lazy" alt={`${title}: ${body}`}/>
            <figcaption>{title}</figcaption>
          </figure>)}
        </div>
        <p className="guide-demo-note">{content.demoNote}</p>
      </section>

      <section aria-labelledby="difference-heading">
        <h2 id="difference-heading">{content.differenceHeading}</h2>
        <div className="guide-comparison"><article><h3>{content.regularTitle}</h3><p>{content.regularBody}</p></article><article><h3>{content.bloomTitle}</h3><p>{content.bloomBody}</p></article></div>
      </section>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading">{content.howHeading}</h2>
        <ol className="guide-how">{content.howSteps.map(([title, body]) => <li key={title}><h3>{title}</h3><p>{body}</p></li>)}</ol>
      </section>

      <section aria-labelledby="limits-heading">
        <h2 id="limits-heading">{content.limitsHeading}</h2>
        <ul className="guide-limits">{content.limits.map(item => <li key={item}>{item}</li>)}</ul>
      </section>
      <div className="guide-end"><p>{content.closing}</p><a className="guide-cta" href="/#headline">{content.tryTool} <span aria-hidden="true">→</span></a></div>
    </main>
    <footer className="guide-footer">
      <span>Slides Bloom · <a href="/">{content.back}</a></span>
      <span>{translate(locale, "footerAuthor")} <a href={authorUrl} target="_blank" rel="noopener noreferrer">{authorName}</a></span>
      <a href={repositoryUrl} target="_blank" rel="noopener noreferrer">{translate(locale, "footerSource")}</a>
    </footer>
  </div>;
}
