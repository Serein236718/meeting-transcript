#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `tmeet record transcript-get` 返回的 JSON 转换成按发言人合并的纯文本段落。

用法：
    python3 build_transcript.py transcript.json                # 段落输出到 stdout
    python3 build_transcript.py transcript.json --out blocks.txt
    python3 build_transcript.py transcript.json --width 0      # 不折行

输出格式（每段一行）：
    [mm:ss] 姓名：原话文本
同一发言人连续发言会被合并为一段，起始时间取首句时间。

统计数据（段落数 / 发言人分布 / 时间范围）输出到 stderr，不污染正文。
"""

import argparse
import json
import sys


def load_minutes(path):
    """读取转写 JSON，返回 (paragraphs, meta)。兼容 {data:{minutes:...}} 与裸 minutes 两种结构。"""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    data = raw.get("data", raw)
    minutes = data.get("minutes") or data
    paragraphs = minutes.get("paragraphs") or []
    if not paragraphs:
        raise SystemExit("未在 JSON 中找到 data.minutes.paragraphs，请确认是 transcript-get 的输出")
    return paragraphs, minutes


def sentence_text(sentence):
    """取一句话的文本：优先拼接 words[].text，退化到 sentence.text。"""
    words = sentence.get("words")
    if words:
        return "".join(w.get("text", "") for w in words)
    return sentence.get("text", "")


def paragraph_text(paragraph):
    return "".join(sentence_text(s) for s in paragraph.get("sentences", [])).strip()


def merge_blocks(paragraphs):
    """按发言人合并连续段落 -> [(speaker, start, end, text), ...]"""
    blocks = []
    for p in paragraphs:
        speaker = (p.get("speaker") or {}).get("user_name") or "未知发言人"
        text = paragraph_text(p)
        if not text:
            continue
        start, end = p.get("start_time", "00:00"), p.get("end_time", "00:00")
        if blocks and blocks[-1][0] == speaker:
            blocks[-1][3] += " " + text
            blocks[-1][2] = end
        else:
            blocks.append([speaker, start, end, text])
    return blocks


def wrap(text, width):
    """按宽度折行，续行缩进 7 格以对齐时间戳之后的正文。"""
    if width <= 0 or len(text) <= width:
        return text
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= width and ch in " ，。！？；：,.!?;:":
            out.append(line.rstrip())
            line = ""
    if line.strip():
        out.append(line.rstrip())
    return ("\n" + " " * 7).join(out)


def main():
    ap = argparse.ArgumentParser(description="转写 JSON -> 按发言人合并的纯文本段落")
    ap.add_argument("json_path")
    ap.add_argument("--out", help="输出文件路径，默认写 stdout")
    ap.add_argument("--width", type=int, default=76, help="正文折行宽度，0 表示不折行（默认 76）")
    args = ap.parse_args()

    paragraphs, _ = load_minutes(args.json_path)
    blocks = merge_blocks(paragraphs)

    speakers, total_sentences = {}, 0
    for p in paragraphs:
        name = (p.get("speaker") or {}).get("user_name") or "未知发言人"
        speakers[name] = speakers.get(name, 0) + 1
        total_sentences += len(p.get("sentences", []))

    lines = []
    for speaker, start, end, text in blocks:
        lines.append("[%s] %s：%s" % (start, speaker, wrap(text, args.width)))
    body = "\n\n".join(lines)

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(body + "\n")

    dist = "、".join("%s %d段" % (k, v) for k, v in speakers.items())
    sys.stderr.write(
        "段落数 %d（合并后 %d 段）｜句子数 %d｜%s｜时间范围 %s-%s\n"
        % (len(paragraphs), len(blocks), total_sentences, dist,
           blocks[0][1] if blocks else "-", blocks[-1][2] if blocks else "-")
    )
    if not args.out:
        sys.stdout.write(body + "\n")


if __name__ == "__main__":
    main()
