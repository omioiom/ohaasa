import requests
import json
import os
import math
import random
import re
import datetime
import time
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==========================================
# [설정] 인스타그램 및 API 설정
# ==========================================
INSTAGRAM_ACCESS_TOKEN = "EAAd6uwZBluwsBQraZBXkNCmgfib8ZB5gEPYOv5OIGuX1ZC6cSUTY5X2HI93XydyaEZCq99tjBuPURHOlc9DybydWoZCV7A8ZCeHuAWaI4lVnfRCximXPKF8VYmiGfgH0y5hGPV6tq28DoZCaZBHqsKuONZAy8CFD7D28JdnlkiGCKjb4uoOj8f0h372yqVezBv"
INSTAGRAM_ACCOUNT_ID = "17841449814829956"
GEMINI_API_KEY = "AIzaSyA2zmmUog9Ohd0XEiviwM2WS9PYPZjJDio"

# ==========================================
# [공통] 매핑 테이블 및 디자인 설정 (기존 디자인 유지)
# ==========================================
SIGN_MAP = {
    "01": "양자리", "02": "황소자리", "03": "쌍둥이자리", "04": "게자리",
    "05": "사자자리", "06": "처녀자리", "07": "천칭자리", "08": "전갈자리",
    "09": "사수자리", "10": "염소자리", "11": "물병자리", "12": "물고기자리"
}

SIGN_ASSET_MAP = {
    "양자리": "Aries",       "황소자리": "Taurus",    "쌍둥이자리": "Gemini",
    "게자리": "Cancer",      "사자자리": "Leo",        "처녀자리": "Virgo",
    "천칭자리": "Libra",     "전갈자리": "Scorpio",    "사수자리": "Sagittarius",
    "염소자리": "Capricorn", "물병자리": "Aquarius",   "물고기자리": "Pisces",
}

IMG_W, IMG_H = 1080, 1350 
FONT_DIR = "nanum-gothic"

# 컬러 팔레트 (기존 유지)
BG           = (251, 248, 242)
BG_CARD      = (247, 244, 238)
BG_HEADER    = (245, 241, 235)
TEXT_DARK    = ( 45,  41,  35)
TEXT_MID     = (130, 122, 108)
TEXT_LIGHT   = (185, 177, 162)
LINE         = (225, 218, 205)
ACCENT       = (164, 120,  88)
ACCENT_LIGHT = (225, 202, 185)
ACCENT_PALE  = (248, 242, 235)
RANK_GOLD    = (195, 168,  90)
RANK_SILVER  = (165, 163, 160)
RANK_BRONZE  = (178, 136, 108)
RANK_BASE    = (185, 177, 162)

# ==========================================
# [기능 1] 데이터 수집 및 Gemini 번역
# ==========================================
def fetch_and_translate_ohaasa():
    ASAHI_URL = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"
    
    print("아사히 TV 데이터 로드 중...")
    response = requests.get(ASAHI_URL)
    response.raise_for_status()
    raw_data = response.json()
    
    today_info = raw_data[0]
    date_str = today_info['onair_date']
    details = today_info['detail']
    
    items_to_translate = []
    for item in details:
        text_parts = [t.strip() for t in item['horoscope_text'].split('\t') if t.strip()]
        luck_item_jp = text_parts[-1] if text_parts else ""
        content_jp = " ".join(text_parts[:-1]) if len(text_parts) > 1 else ""
        
        items_to_translate.append({
            "rank": int(item['ranking_no']),
            "st": item['horoscope_st'],
            "content": content_jp,
            "luck": luck_item_jp
        })

    # Gemini 2.5-flash만 사용
    prompt = f"Translate the following JSON list into natural Korean. Maintain the 'rank' and 'st' fields. Translate 'content' and 'luck' only. Return ONLY the JSON: {json.dumps(items_to_translate, ensure_ascii=False)}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    print("Google Gemini(2.5-flash) 번역 요청 중...")
    GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    res = requests.post(GEMINI_URL, json=payload, timeout=60).json()
    translated_text = res['candidates'][0]['content']['parts'][0]['text']
    translated_list = json.loads(translated_text)
    final_results = []
    for i, item in enumerate(translated_list):
        final_results.append({
            "rank": item['rank'],
            "sign": SIGN_MAP.get(item['st'], "알 수 없음"),
            "content": item['content'],
            "luck_item": item['luck']
        })
    final_results.sort(key=lambda x: x['rank'])
    return {"date": date_str, "results": final_results}

# ==========================================
# [기능 2] 이미지 생성 헬퍼 (기존 디자인 유지)
# ==========================================
def find_nanum_fonts():
    if not os.path.isdir(FONT_DIR): return (None, None)
    ttf_files = [f for f in os.listdir(FONT_DIR) if f.lower().endswith('.ttf')]
    bold = [f for f in ttf_files if 'bold' in f.lower()][0] if [f for f in ttf_files if 'bold' in f.lower()] else None
    reg = [f for f in ttf_files if 'bold' not in f.lower()][0] if [f for f in ttf_files if 'bold' not in f.lower()] else None
    return (os.path.join(FONT_DIR, bold) if bold else None, os.path.join(FONT_DIR, reg) if reg else None)

def get_font(path, size):
    try: return ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except: return ImageFont.load_default()

def make_solid_bg(w, h, color=BG):
    img = Image.new('RGB', (w, h), color)
    draw = ImageDraw.Draw(img)
    rng = random.Random(99)
    for _ in range(3000):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        v = rng.randint(0, 5)
        base = [max(0, min(255, b - v)) for b in list(color)]
        draw.point((x, y), fill=tuple(base))
    return img

def draw_centered(draw, text, font, cy, color, w=IMG_W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, cy), text, fill=color, font=font)

def wrap_text_kr(draw, text, font, max_width):
    lines, current = [], ""
    for char in text:
        test = current + char
        if draw.textlength(test, font=font) <= max_width: current = test
        else:
            if current: lines.append(current)
            current = char
    if current: lines.append(current)
    return lines

def rank_color(rank):
    if rank == 1: return RANK_GOLD
    elif rank == 2: return RANK_SILVER
    elif rank == 3: return RANK_BRONZE
    return RANK_BASE

def draw_soft_circle_on_image(img, cx, cy, radius, color, blur_radius=40):
    layer = Image.new('RGBA', (IMG_W, IMG_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r, g, b = color
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(r, g, b, 40))
    layer = layer.filter(ImageFilter.GaussianBlur(blur_radius))
    base = img.convert('RGBA')
    return Image.alpha_composite(base, layer).convert('RGB')

def load_sign_image(sign_name, target_size=180):
    asset_name = SIGN_ASSET_MAP.get(sign_name)
    if not asset_name: return None
    asset_path = os.path.join('asset', 'stars', f"{asset_name}.png")
    if not os.path.exists(asset_path): return None
    try:
        raw = Image.open(asset_path).convert("RGBA")
        raw.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
        r_ch, g_ch, b_ch, a_ch = raw.split()
        return Image.merge("RGBA", (
            a_ch.point(lambda v: int(v * ACCENT[0] / 255)),
            a_ch.point(lambda v: int(v * ACCENT[1] / 255)),
            a_ch.point(lambda v: int(v * ACCENT[2] / 255)),
            a_ch
        ))
    except: return None

def _weekday_kr(date_str):
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]))
    return ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]

def draw_detail_section(img, item, start_y, fonts):
    draw = ImageDraw.Draw(img)
    rc = rank_color(item['rank'])
    draw.text((110, start_y + 30), f"RANK", fill=TEXT_LIGHT, font=fonts['label_sm'])
    draw.text((110, start_y + 60), str(item['rank']), fill=rc, font=fonts['rank_md'])
    draw.text((110, start_y + 165), item['sign'], fill=TEXT_DARK, font=fonts['sign_md'])

    ICX, ICY = 790, start_y + 115
    IR = 100 
    img = draw_soft_circle_on_image(img, ICX, ICY, IR+35, ACCENT_PALE, 35)
    draw = ImageDraw.Draw(img)
    draw.ellipse([ICX-IR, ICY-IR, ICX+IR, ICY+IR], outline=LINE, width=1)
    
    sign_img = load_sign_image(item['sign'], target_size=int(IR*1.7))
    if sign_img:
        img.paste(sign_img, (int(ICX - sign_img.width//2), int(ICY - sign_img.height//2)), sign_img)
        draw = ImageDraw.Draw(img)

    content_y = start_y + 275
    lines = wrap_text_kr(draw, item['content'], fonts['content_sm'], IMG_W - 220 - 40)
    if lines:
        quote_l, quote_r = "\u201C", "\u201D"
        x0 = 110
        draw.text((x0, content_y), quote_l, fill=TEXT_DARK, font=fonts['lucky_sm'])
        ql_w = draw.textbbox((0, 0), quote_l, font=fonts['lucky_sm'])[2]
        for idx, line in enumerate(lines):
            draw.text((x0 + (ql_w if idx==0 else 0), content_y), line, fill=TEXT_DARK, font=fonts['content_sm'])
            if idx == len(lines)-1:
                lw = draw.textlength(line, font=fonts['content_sm'])
                draw.text((x0 + (ql_w if len(lines)==1 else 0) + lw, content_y), quote_r, fill=TEXT_DARK, font=fonts['lucky_sm'])
            content_y += 50

    card_y = start_y + 440
    card_h = 100
    draw.rounded_rectangle([110, card_y, IMG_W-110, card_y+card_h], radius=12, fill=BG_CARD, outline=LINE)
    draw.rounded_rectangle([110, card_y, 120, card_y+card_h], radius=12, fill=ACCENT_LIGHT)
    draw.text((150, card_y + 20), "LUCKY ITEM", fill=TEXT_LIGHT, font=fonts['label_xs'])
    draw.text((150, card_y + 48), item['luck_item'], fill=ACCENT, font=fonts['lucky_sm'])
    return img

# ==========================================
# [기능 3] 호스팅 (imgdb 실패 시 Litterbox 사용)
# ==========================================
def upload_image(file_path):
    # imgDB 먼저 시도, 실패(연결 오류 등) 시 Litterbox로 시도
    url = "https://imgdb.net/api/upload"
    try:
        with open(file_path, 'rb') as f:
            files = {'image': f}
            data = {'key': 'public_api_key', 'format': 'json'}
            response = requests.post(url, data=data, files=files, timeout=30)
        if response.status_code == 200:
            res = response.json()
            if res.get('status_code') == 200 and 'image' in res:
                link = res['image']['url']
                print(f"  [imgDB] 업로드 성공: {link}")
                return link
            else:
                print(f"  [imgDB] 응답 오류: {res}")
        else:
            print(f"  [imgDB] HTTP 오류: {response.status_code}")
    except Exception as e:
        err_str = str(e)
        print(f"  [imgDB] 오류: {err_str}")
        # imgDB 연결 오류 감지 시 Litterbox로 대체
        if 'Failed to establish a new connection' in err_str or 'Connection refused' in err_str or 'Max retries exceeded' in err_str:
            print("  [imgDB] 연결 오류 감지, Litterbox로 대체 시도...")
            return upload_to_litterbox(file_path)
    # 기타 실패 시에도 Litterbox로 시도
    return upload_to_litterbox(file_path)

def upload_to_litterbox(file_path):
    try:
        url = "https://litterbox.catbox.moe/resources/internals/api.php"
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload', 'time': '1h'}
            response = requests.post(url, data=data, files=files, timeout=60)
        if response.status_code == 200:
            link = response.text.strip()
            if link.startswith("http"):
                print(f"  [Litterbox] 업로드 성공: {link}")
                return link
        print(f"  [Litterbox] 응답 오류: {response.text}")
    except Exception as e:
        print(f"  [Litterbox] 연결 오류: {e}")
    return None

def update_last_upload(date_str):
    with open("last_upload.txt", "w") as f:
        f.write(date_str)
    print(f"기록 업데이트 완료: {date_str}")

def post_to_instagram_reels(video_path, caption, date_str):
    print(f"인스타그램 릴스 업로드 시작: {video_path}")
    video_url = upload_to_litterbox(video_path)
    if not video_url: return False

    res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption, "access_token": INSTAGRAM_ACCESS_TOKEN
    }).json()

    if "id" in res:
        creation_id = res["id"]
        for _ in range(20):
            time.sleep(5)
            status = requests.get(f"https://graph.facebook.com/v18.0/{creation_id}?fields=status_code&access_token={INSTAGRAM_ACCESS_TOKEN}").json()
            if status.get("status_code") == "FINISHED":
                time.sleep(10)
                pub = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish", data={
                    "creation_id": creation_id, "access_token": INSTAGRAM_ACCESS_TOKEN
                }).json()
                if "id" in pub:
                    print(f"🎉 릴스 포스팅 성공!")
                    update_last_upload(date_str) # 릴스 성공 즉시 기록 (순서 보장)
                    return True
                break
    return False

def post_to_instagram(image_urls, caption, date_str):
    print(f"인스타그램 피드 업로드 중...")
    container_ids = []
    for url in image_urls:
        res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media", 
                            data={"image_url": url, "is_carousel_item": "true", "access_token": INSTAGRAM_ACCESS_TOKEN}).json()
        if "id" in res: container_ids.append(res["id"])
    
    if len(container_ids) < len(image_urls): return False

    album_res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media", data={
        "media_type": "CAROUSEL", "children": ",".join(container_ids), "caption": caption, "access_token": INSTAGRAM_ACCESS_TOKEN
    }).json()
    
    if "id" in album_res:
        time.sleep(10)
        pub = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish", 
                            data={"creation_id": album_res["id"], "access_token": INSTAGRAM_ACCESS_TOKEN}).json()
        if "id" in pub:
            print(f"🎉 피드 포스팅 성공!")
            update_last_upload(date_str) # 성공 즉시 기록
            return True
    return False

# ==========================================
# [기능 4] 메인 프로세스
# ==========================================
def main():
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = kst_now.strftime("%Y%m%d")

    try:
        fetched_data = fetch_and_translate_ohaasa()
        target_date = fetched_data['date']
        
        output_dir = "ohaasa_final_post"
        os.makedirs(output_dir, exist_ok=True)

        results = fetched_data['results']
        date_display = f"{target_date[:4]}.{target_date[4:6]}.{target_date[6:]} {_weekday_kr(target_date)}요일"

        bold_p, reg_p = find_nanum_fonts()
        fonts = {
            'brand': get_font(reg_p, 22), 'date': get_font(reg_p, 26), 'title': get_font(bold_p, 58),
            'rank_sm': get_font(bold_p, 42), 'rank_md': get_font(bold_p, 70), 'sign_sm': get_font(reg_p, 50),
            'sign_md': get_font(bold_p, 52), 'label_sm': get_font(reg_p, 18), 'label_xs': get_font(reg_p, 15),
            'content_sm': get_font(reg_p, 30), 'lucky_sm': get_font(bold_p, 36)
        }

        image_paths = []
        print("이미지 생성 시작...")

        # 1. 요약 이미지
        img_s = make_solid_bg(IMG_W, IMG_H)
        draw_s = ImageDraw.Draw(img_s)
        draw_s.rectangle([0, 0, IMG_W, 250], fill=BG_HEADER)
        draw_centered(draw_s, "OHAASA FORTUNE", fonts['brand'], 55, TEXT_LIGHT)
        draw_centered(draw_s, f"{int(target_date[4:6])}/{int(target_date[6:8])} 오하아사", fonts['title'], 100, TEXT_DARK)
        draw_centered(draw_s, date_display, fonts['date'], 190, TEXT_MID)
        
        y_cur, ROW_H = 280, 82
        for item in results:
            rc, rs = rank_color(item['rank']), str(item['rank'])
            center_y = y_cur + (ROW_H // 2)
            r_w = draw_s.textbbox((0, 0), rs, font=fonts['rank_sm'])[2]
            draw_s.text((400 - r_w, center_y - 21), rs, fill=rc, font=fonts['rank_sm'])
            s_icon = load_sign_image(item['sign'], 50)
            if s_icon: img_s.paste(s_icon, (int(485 - s_icon.width//2), int(center_y - s_icon.height//2 - 3)), s_icon)
            draw_s.text((560, center_y - 25), item['sign'], fill=TEXT_DARK, font=fonts['sign_sm'])
            draw_s.line([(180, y_cur + ROW_H), (IMG_W - 180, y_cur + ROW_H)], fill=LINE, width=1)
            y_cur += ROW_H
        
        path_s = os.path.join(output_dir, "00_summary.png")
        img_s.save(path_s); image_paths.append(path_s)

        # 2. 상세 이미지
        results_reversed = results[::-1] 
        for i in range(0, len(results_reversed), 2):
            pair = results_reversed[i:i+2]
            img = make_solid_bg(IMG_W, IMG_H); draw = ImageDraw.Draw(img)
            draw_centered(draw, f"OHAASA | {date_display}", fonts['brand'], 40, TEXT_LIGHT)
            draw.line([(100, 80), (IMG_W-100, 80)], fill=LINE, width=1)
            img = draw_detail_section(img, pair[0], 95, fonts)
            if len(pair) > 1:
                draw = ImageDraw.Draw(img); draw.line([(80, IMG_H//2), (IMG_W-80, IMG_H//2)], fill=LINE, width=1)
                img = draw_detail_section(img, pair[1], IMG_H//2 + 15, fonts)
            draw = ImageDraw.Draw(img); draw_centered(draw, "FOR YOUR LUCKY DAY", fonts['brand'], IMG_H - 65, TEXT_LIGHT)
            path_d = os.path.join(output_dir, f"detail_{i//2 + 1}.png")
            img.save(path_d); image_paths.append(path_d)

        # 3. 영상 생성 및 릴스
        try:
            import cv2
            import subprocess
            import glob
            video_path = os.path.join(output_dir, f"ohaasa_{today_str}.mp4")
            first_img = cv2.imread(image_paths[0])
            h, w, _ = first_img.shape
            out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'mp4v'), 24, (w, h))
            for idx, p in enumerate(image_paths):
                frame = cv2.imread(p)
                for _ in range((2 if idx == 0 else 4) * 24): out.write(frame)
            out.release()
            
            video_final = video_path
            mp3_files = glob.glob(os.path.join("asset", "mp3", "m*.mp3"))
            if mp3_files:
                bgm_path = random.choice(mp3_files)
                video_bgm = os.path.join(output_dir, f"ohaasa_{today_str}_bgm.mp4")
                subprocess.run(["ffmpeg", "-y", "-i", video_path, "-i", bgm_path, "-c:v", "copy", "-c:a", "aac", "-shortest", video_bgm], check=True)
                video_final = video_bgm

            post_to_instagram_reels(video_final, f"🔮 {date_display} 오하아사 별자리 운세", target_date)
        except Exception as ve: print(f"영상 오류: {ve}")

        # 4. 피드 포스팅
        public_urls = []
        for p in image_paths:
            u = upload_image(p) # imgDB 대신 바로 Litterbox 사용 시도
            if u: public_urls.append(u)
        
        if len(public_urls) == len(image_paths):
            post_to_instagram(public_urls, f"🔮 {date_display} 오하아사 오늘의 운세", target_date)

    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    main()