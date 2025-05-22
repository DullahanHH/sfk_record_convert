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
    "学生签名": {"box": ((490, 2650), (880, 2780)), "max_font_size": 64},
    "导师签名": {"box": ((1440, 2650), (1830, 2780)), "max_font_size": 64},
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

    # 作业完成情况
    hw_status_check(draw, font_path, data_dict);

    # 签名填入
    if signature_img:
        draw_signature(image, signature_img, position_map["导师签名"]["box"])
    if signature_img_student:
        draw_signature(image, signature_img_student, position_map["学生签名"]["box"])

    return image

def hw_status_check(draw, font_path, entry):
    checkbox_map = {
        "完成": (1420, 2580),
        "未完成": (1980, 2580)
    }
    hw_status = entry.get("上次作业完成情况", "").strip()
    if hw_status in checkbox_map:
        check_pos = checkbox_map[hw_status]
        draw.text(check_pos, "✔", fill="green", font=ImageFont.truetype(font_path, 64))

def draw_signature(image, signature_img, box):
    (x1, y1), (x2, y2) = box
    target_height = y2 - y1

    scale = target_height / signature_img.height
    new_width = int(signature_img.width * scale)
    resized = signature_img.resize((new_width, target_height))

    center_x = x1 + (x2 - x1 - new_width) // 2
    image.paste(resized, (center_x, y1), resized)

def parse_csv(uploaded_file):
    # 1. 读取完整文本，解码为字符串
    raw = uploaded_file.read().decode('utf-8')
    # 2. 使用 StringIO 包装，以便 csv.reader 正确处理内容
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)

    if not rows:
        return []

    max_blocks = len(rows[0]) // 2
    all_entries = []

    for b in range(max_blocks):
        entry = {}
        is_empty_block = True

        for row in rows:
            if len(row) > b * 2 + 1:
                key = row[b * 2].strip()
                value = row[b * 2 + 1].strip()
                # 只在 key 或 value 至少一个非空时记录
                if key or value:
                    entry[key] = value
                    is_empty_block = False

        if not is_empty_block:
            all_entries.append(entry)
        else:
            # 如果该块是空的，我们认为后面也没用了，提前退出
            break

    for e in all_entries:
        try:
            e["_parsed_date"] = datetime.strptime(e.get("上课日期", ""), "%Y-%m-%d")
        except Exception:
            e["_parsed_date"] = datetime.min

    all_entries.sort(key=lambda x: x["_parsed_date"])   # 根据日期排序
    return all_entries


# === Streamlit UI ===
st.title("📋 课程记录表生成器")
st.write("请上传课程记录CSV文件：")

uploaded_file = st.file_uploader("选择CSV文件", type=["csv"])
start_index = st.number_input("从第几次课开始？", min_value=1, value=1, step=1)
signature_file = st.file_uploader("上传导师签名（可选）", type=["png", "jpg", "jpeg"])
hidden_file = None

if "hide_clicks" not in st.session_state:
    st.session_state.hide_clicks = 0
if st.session_state.hide_clicks >= 5:
    hidden_file = st.file_uploader("上传学生签名", type=["png", "jpg", "jpeg"])

signature_img = None
signature_img_student = None

if signature_file is not None:
    signature_img = Image.open(signature_file).convert("RGBA")

if hidden_file is not None:
    signature_img_student = Image.open(hidden_file).convert("RGBA")

if uploaded_file is not None:
    records = parse_csv(uploaded_file)
    st.success(f"成功读取 {len(records)} 条记录")

    result_images = []
    for idx, entry in enumerate(records):
        entry["第几次课"] = f"{start_index + idx}"
        img = fill_image(TEMPLATE_PATH, entry, position_map, FONT_PATH, FONT_SIZE, SHOW_BOXES)

        buf = BytesIO()
        img.save(buf, format="PNG")
        result_images.append((f"record_{idx + 1}.png", buf.getvalue()))

    # 先展示所有生成的图片
    for filename, data in result_images:
        st.image(data, caption=filename)
        st.download_button("下载图像", data, file_name=filename, mime="image/png")

    # 然后一次性打包为 zip 并提供下载
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zipf:
        for filename, data in result_images:
            zipf.writestr(filename, data)
    zip_buf.seek(0)

    st.write("")
    st.write("")
    st.write("")
    st.write("一键下载：")
    st.download_button(
        label="📥 下载所有记录表（ZIP）",
        data=zip_buf,
        file_name="课程记录表合集.zip",
        mime="application/zip"
    )

if st.button(""):
    st.session_state.hide_clicks += 1

st.markdown("""
<hr style="margin-top: 50px;"/>
<div style="text-align: center; color: gray; font-size: 0.8em;">
    © 2025 By Jianchun Zhou. SFK Haidian.
</div>
""", unsafe_allow_html=True)