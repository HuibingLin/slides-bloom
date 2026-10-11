"""Stable error codes for clients to display in their chosen language."""

ERROR_CODES = {
    "无效任务编号": "invalidJob",
    "请选择不超过 20MB 的 .pptx 文件": "invalidUpload",
    "上传任务不存在或已过期": "expiredUpload",
    "分片编号超出范围": "chunkIndex",
    "文件不是有效的 PPTX 演示文稿": "invalidPptx",
    "解压后文件超过安全上限": "expandedTooLarge",
    "不支持加密的 PPTX 文件": "encryptedPptx",
    "PPTX 中有超出安全上限的单个文件": "embeddedTooLarge",
    "PPTX 中的 XML 内容超过安全上限": "xmlTooLarge",
    "当前任务不能合并": "cannotAssemble",
    "仍有分片尚未上传": "missingChunks",
    "文件大小校验失败": "sizeMismatch",
    "上传已结束": "uploadEnded",
    "分片大小超出限制": "chunkTooLarge",
    "分片长度不正确": "chunkLength",
    "分片校验失败": "chunkChecksum",
    "无效的 Content-Length": "invalidLength",
    "请求体超过 20MB 上限": "requestTooLarge",
    "PDF 尚未生成": "pdfNotReady",
    "幻灯片关系缺失": "missingSlideRelation",
    "幻灯片路径无效": "invalidSlidePath",
    "演示文稿没有幻灯片": "noSlides",
    "演示文稿没有幻灯片目录": "missingSlideList",
    "幻灯片内部名称冲突": "slideNameConflict",
    "无法展开幻灯片动画": "cannotExpand",
}


def error_code(message: str) -> str:
    if message.startswith("幻灯片 ") and message.endswith(" 的动画无法按原顺序准确展开"):
        return "unsupportedAnimation"
    if message in ERROR_CODES:
        return ERROR_CODES[message]
    if message.startswith("展开后超过 "):
        return "tooManyPages"
    if message.startswith("LibreOffice 渲染失败："):
        return "renderFailed"
    if message.startswith("PDF 页数校验失败："):
        return "pdfPageMismatch"
    return "conversionFailed"
