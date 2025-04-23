import streamlit as st
import io, csv, os
import zipfile

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime


# === 设置 ===
TEMPLATE_PATH = "记录表模板.jpg"
FONT_PATH = "simhei.ttf"
FONT_SIZE = 64
SHOW_BOXES = False
AUTO_FONT_SIZE = True

position_map = {
    "课程名称": {"box": ((520, 1084), (2250, 1255)), "max_font_size": 64},
    "上课日期": {"box": ((520, 1254), (806, 1418)), "max_font_size": 50},
    "第几次课": {"box": ((916, 1314), (982, 1360)), "max_font_size": 64},
    "上课时间": {"box": ((1390, 1257), (1671, 1418)), "max_font_size": 64},
    "下课时间": {"box": ((1960, 1257), (2250, 1418)), "max_font_size": 64},
    "上课内容": {"box": ((540, 1436), (2220, 1989)), "max_font_size": 50},
    "作业内容": {"box": ((538, 2031), (2230, 2468)), "max_font_size": 50},
}

def wrap_line_by_width(line, font, max_width):
    words = list(line)
    wrapped_lines = []
    current_line = ""
    for ch in words:
        test_line = current_line + ch
        bbox = font.getbbox(test_line)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current_line = test_line
        else:
            if current_line:
                wrapped_lines.append(current_line)
            current_line = ch
    if current_line:
        wrapped_lines.append(current_line)
    return wrapped_lines

def draw_text_centered(draw, text, box, font_path, font_size,
                       fill="black", show_border=False, auto_font_size=True):
    (x1, y1), (x2, y2) = box
    box_w, box_h = x2 - x1, y2 - y1

    # 自动缩放字体以适应总高度
    while True:
        font = ImageFont.truetype(font_path, font_size)
        # 第一步：拆分并断行，同时保留空行
        lines = []
        for raw in text.split('\n'):
            if raw == "":
                lines.append("")  # 空行
            else:
                lines += wrap_line_by_width(raw, font, box_w)

        # 计算每行高度，空行用 font_size * 1.2 作为行高
        lh = font_size + int(font_size * 0.2)
        total_h = len(lines) * lh - int(font_size * 0.2)

        if not auto_font_size or (total_h <= box_h and font_size > 10):
            break
        font_size -= 1
        if font_size < 10:
            break

    # 垂直居中起点
    y = y1 + (box_h - total_h) / 2
    for line in lines:
        if line == "":
            y += lh
            continue
        w = font.getbbox(line)[2] - font.getbbox(line)[0]
        x = x1 + (box_w - w) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += lh

    if show_border:
        draw.rectangle([x1, y1, x2, y2], outline="red", width=1)

def fill_image(template_path, data_dict, position_map, font_path, global_font_size, show_boxes=False):
    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    for key, config in position_map.items():
        value = data_dict.get(key, "")
        box = config["box"]
        max_font_size = config.get("max_font_size", global_font_size)
        draw_text_centered(
            draw, value, box, font_path, max_font_size,
            fill="black", show_border=show_boxes, auto_font_size=True
        )
    return image

def parse_csv(uploaded_file):
    # 1. 直接拿回完整的文本，不 splitlines()
    raw = uploaded_file.read().decode('utf-8')
    # 2. 用 StringIO 包装，让 csv.reader 处理多行单元格
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)

    num_columns = len(rows[0])
    num_blocks  = num_columns // 2
    all_entries = []

    for b in range(num_blocks):
        entry = {}
        for row in rows:
            if len(row) > b*2 + 1:
                key   = row[b*2].strip()
                value = row[b*2+1]
                entry[key] = value
        all_entries.append(entry)

    for e in all_entries:
        try:
            e["_parsed_date"] = datetime.strptime(e.get("上课日期",""), "%Y-%m-%d")
        except:
            e["_parsed_date"] = datetime.min
    all_entries.sort(key=lambda x: x["_parsed_date"])
    return all_entries

# === Streamlit UI ===
st.title("📋 课程记录表生成器")
st.write("请上传课程记录CSV文件：")

uploaded_file = st.file_uploader("选择CSV文件", type=["csv"])
if uploaded_file is not None:
    records = parse_csv(uploaded_file)
    st.success(f"成功读取 {len(records)} 条记录")

    result_images = []
    for idx, entry in enumerate(records):
        entry["第几次课"] = f"{idx + 1}"
        img = fill_image(TEMPLATE_PATH, entry, position_map, FONT_PATH, FONT_SIZE, SHOW_BOXES)

        buf = BytesIO()
        img.save(buf, format="PNG")
        result_images.append((f"record_{idx + 1}.png", buf.getvalue()))

    # 先展示所有生成的图片
    for filename, data in result_images:
        st.image(data, caption=filename)

    # 然后一次性打包为 zip 并提供下载
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zipf:
        for filename, data in result_images:
            zipf.writestr(filename, data)
    zip_buf.seek(0)

    st.download_button(
        label="📥 下载所有记录表（ZIP）",
        data=zip_buf,
        file_name="课程记录表合集.zip",
        mime="application/zip"
    )
