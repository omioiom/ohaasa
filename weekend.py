def post_to_instagram_reels(video_path, caption):
    print(f"인스타그램 릴스 업로드 시작: {video_path}")
    upload_url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media"
    publish_url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    # 릴스 업로드는 video_url 방식 사용
    # 먼저 catbox에 업로드
    video_url = upload_to_catbox(video_path)
    if not video_url:
        print("릴스 영상 catbox 업로드 실패")
        return False
    # Instagram 컨테이너 생성
    res = requests.post(upload_url, data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }).json()
    if "id" in res:
        creation_id = res["id"]
        print(f"릴스 컨테이너 생성 완료(ID: {creation_id})")
        # 컨테이너 준비 상태 polling (최대 60초)
        for i in range(12):
            time.sleep(5)
            status_url = f"https://graph.facebook.com/v18.0/{creation_id}?fields=status_code&access_token={INSTAGRAM_ACCESS_TOKEN}"
            status_res = requests.get(status_url).json()
            status_code = status_res.get("status_code", "")
            print(f"릴스 컨테이너 상태: {status_code}")
            if status_code == "FINISHED":
                publish_res = requests.post(publish_url, data={
                    "creation_id": creation_id,
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }).json()
                if "id" in publish_res:
                    print(f"🎉 릴스 포스팅 성공! ID: {publish_res['id']}")
                    return True
                else:
                    print(f"❌ 릴스 최종 발행 실패: {publish_res}")
                break
            elif status_code == "ERROR":
                print(f"❌ 릴스 컨테이너 오류: {status_res}")
                break
        else:
            print("❌ 릴스 컨테이너 준비 시간 초과")
    else:
        print(f"❌ 릴스 컨테이너 생성 실패: {res}")
    return False
import cv2
import requests
import json
import os
import math
import random
import re
import datetime
import time
import sys
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==========================================
# [설정] 인스타그램 설정
# ==========================================
INSTAGRAM_ACCESS_TOKEN = "EAAd6uwZBluwsBQraZBXkNCmgfib8ZB5gEPYOv5OIGuX1ZC6cSUTY5X2HI93XydyaEZCq99tjBuPURHOlc9DybydWoZCV7A8ZCeHuAWaI4lVnfRCximXPKF8VYmiGfgH0y5hGPV6tq28DoZCaZBHqsKuONZAy8CFD7D28JdnlkiGCKjb4uoOj8f0h372yqVezBv"
INSTAGRAM_ACCOUNT_ID = "17841449814829956"

# ==========================================
# [공통] 매핑 테이블 및 디자인 설정
# ==========================================
SIGN_MAP_JP = {
    "おひつじ座": "양자리", "おうし座": "황소자리", "ふたご座": "쌍둥이자리", "かに座": "게자리",
    "しし座": "사자자리", "おとめ座": "처녀자리", "てんびん座": "천칭자리", "さそり座": "전갈자리",
    "いて座": "사수자리", "やぎ座": "염소자리", "みずがめ座": "물병자리", "うお座": "물고기자리"
}

SIGN_ASSET_MAP = {
    "양자리": "Aries",       "황소자리": "Taurus",    "쌍둥이자리": "Gemini",
    "게자리": "Cancer",      "사자자리": "Leo",        "처녀자리": "Virgo",
    "천칭자리": "Libra",     "전갈자리": "Scorpio",    "사수자리": "Sagittarius",
    "염소자리": "Capricorn", "물병자리": "Aquarius",   "물고기자리": "Pisces",
}

IMG_W, IMG_H = 1080, 1350 
FONT_DIR = "nanum-gothic"

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
# [기능 1] 데이터 수집 및 번역 (TV 아사히 방식)
# ==========================================
def fetch_and_translate_ohaasa():
    TV_ASAHI_URL = "https://www.tv-asahi.co.jp/goodmorning/uranai/index.html"
    MODEL_SERVER_URL = "http://223.130.130.97:11434/api/generate"
    MODEL_NAME = "gpt-oss:120b"

    try:
        print(f"TV 아사히 데이터 로드 중...")
        response = requests.get(TV_ASAHI_URL)
        response.encoding = response.apparent_encoding 
        soup = BeautifulSoup(response.text, 'html.parser')

        date_raw = soup.select_one('.rank-area .ttl-area').text if soup.select_one('.rank-area .ttl-area') else ""
        date_digits = re.findall(r'\d+', date_raw)
        # 현재 연도 자동 추출
        current_year = datetime.datetime.now().year
        date_str = f"{current_year}{date_digits[0].zfill(2)}{date_digits[1].zfill(2)}" if len(date_digits) >= 2 else datetime.datetime.now().strftime("%Y%m%d")

        items_to_translate = []
        seiza_boxes = soup.select('.seiza-box')
        
        rank_list = {}
        for li in soup.select('.rank-box li'):
            rank_img = li.select_one('img.rank')
            if rank_img:
                rank_num = rank_img['src'].split('-')[-1].split('.')[0]
                sign_name = li.select_one('span').text.strip()
                rank_list[sign_name] = int(rank_num)

        for box in seiza_boxes:
            sign_name_jp = box.select_one('.seiza-txt').text.split('(')[0].strip()
            content_jp = box.select_one('.read').text.strip()
            
            read_area = box.select_one('.read-area').get_text(separator="|").split('|')
            luck_parts = [p.strip() for p in read_area if "：" in p or ":" in p]
            luck_jp = ", ".join(luck_parts)

            items_to_translate.append({
                "rank": rank_list.get(sign_name_jp, 0),
                "sign_jp": sign_name_jp,
                "content": content_jp,
                "luck": luck_jp
            })

        print(f"AI 서버({MODEL_NAME}) 번역 요청 중...")
        prompt = f"""당신은 일본어 전문 번역가입니다. 아래 제공된 일본어 별자리 운세 JSON 데이터의 'content'와 'luck' 필드를 한국어로 자연스럽게 번역하세요.
        만약 content 에 부적절하거나 쓸모없는 이모지나 기호 같은 문자가 포함되어 있다면 이를 제거한 후 번역하세요. 
특히 'luck' 필드에 포함된 'ラッキーカラー(행운의 색)'는 '행운의 색: [색상]', '幸運의 카기(행운의 열쇠/아이템)'는 '행운의 아이템: [아이템]' 형식으로 번역하세요.
결과는 반드시 부연 설명 없이 JSON 코드만 출력하세요.
데이터: {json.dumps(items_to_translate, ensure_ascii=False)}"""

        headers = {"Content-Type": "application/json"}
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}

        resp = requests.post(MODEL_SERVER_URL, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        
        raw_text = resp.json().get("response", "")
        json_str = re.sub(r"```json|```", "", raw_text).strip()
        
        try:
            translated_list = json.loads(json_str)
        except:
            match = re.search(r"(\[.*\])", json_str, re.DOTALL)
            translated_list = json.loads(match.group(1)) if match else []

        final_results = []
        for item in translated_list:
            # sign 필드가 일본어로 올 수도 있고, 번역 결과로 올 수도 있음. 모두 매핑 시도
            sign_jp = item.get('sign_jp') or item.get('sign') or item.get('st') or ''
            sign_kr = SIGN_MAP_JP.get(sign_jp, sign_jp)
            # 혹시 번역 결과가 한글로 잘 들어왔으면 그대로 사용
            if sign_kr not in SIGN_ASSET_MAP:
                # 번역 결과가 한글로 들어온 경우도 체크
                sign_kr = item.get('sign', sign_kr)
            final_results.append({
                "rank": item['rank'],
                "sign": sign_kr,
                "content": item['content'],
                "luck_item": item['luck']
            })
        final_results.sort(key=lambda x: x['rank'])
        return {"date": date_str, "results": final_results}

    except Exception as e:
        print(f"데이터 수집 중 오류: {e}")
        raise

# ==========================================
# [기능 2] 이미지 생성 헬퍼
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
    try:
        d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]))
        return ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
    except: return ""

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
            content_y += 45

    card_y = start_y + 430
    card_h = 110
    draw.rounded_rectangle([110, card_y, IMG_W-110, card_y+card_h], radius=12, fill=BG_CARD, outline=LINE)
    draw.rounded_rectangle([110, card_y, 120, card_y+card_h], radius=12, fill=ACCENT_LIGHT)
    draw.text((150, card_y + 18), "LUCKY COLOR & ITEM", fill=TEXT_LIGHT, font=fonts['label_xs'])
    
    luck_font = fonts['lucky_sm']
    if draw.textlength(item['luck_item'], font=luck_font) > (IMG_W - 300):
        luck_font = fonts['content_sm']
        
    draw.text((150, card_y + 45), item['luck_item'], fill=ACCENT, font=luck_font)
    return img

# ==========================================
# [기능 3] 호스팅 및 인스타그램 (Catbox)
# ==========================================
def upload_to_catbox(file_path):
    try:
        url = "https://catbox.moe/user/api.php"
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload'}
            response = requests.post(url, data=data, files=files, timeout=30)
        if response.status_code == 200:
            link = response.text.strip()
            print(f"  성공: {file_path} -> {link}")
            return link
        return None
    except Exception as e:
        print(f"  오류: {file_path} 업로드 실패 ({e})")
        return None

def post_to_instagram(image_urls, caption):
    print(f"인스타그램 업로드 중 (이미지 {len(image_urls)}장)...")
    container_ids = []
    for i, url in enumerate(image_urls):
        res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media", 
                            data={"image_url": url, "is_carousel_item": "true", "access_token": INSTAGRAM_ACCESS_TOKEN}).json()
        if "id" in res: container_ids.append(res["id"])
        else: print(f"  컨테이너 {i+1} 실패: {res}"); return

    album_res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media",
                              data={"media_type": "CAROUSEL", "children": ",".join(container_ids), "caption": caption, "access_token": INSTAGRAM_ACCESS_TOKEN}).json()
    
    if "id" in album_res:
        creation_id = album_res["id"]
        time.sleep(5)
        publish_res = requests.post(f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish", 
                                    data={"creation_id": creation_id, "access_token": INSTAGRAM_ACCESS_TOKEN}).json()
        if "id" in publish_res: 
            print(f"🎉 포스팅 성공! ID: {publish_res['id']}")
            return True
        else: 
            print(f"❌ 최종 발행 실패: {publish_res}")
    else: 
        print(f"❌ 앨범 생성 실패: {album_res}")
    return False

# ==========================================
# [기능 4] 실행 프로세스 (GitHub Actions 최적화)
# ==========================================
def run_full_process(data):
    output_dir = "ohaasa_final_post"
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    results = data['results']
    date_str = data['date']
    date_display = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]} {_weekday_kr(date_str)}요일"

    bold_p, reg_p = find_nanum_fonts()
    fonts = {
        'brand': get_font(reg_p, 22), 'date': get_font(reg_p, 26), 'title': get_font(bold_p, 58),
        'rank_sm': get_font(bold_p, 42), 'rank_md': get_font(bold_p, 70), 'sign_sm': get_font(reg_p, 50),
        'sign_md': get_font(bold_p, 52), 'label_sm': get_font(reg_p, 18), 'label_xs': get_font(reg_p, 15),
        'content_sm': get_font(reg_p, 30), 'lucky_sm': get_font(bold_p, 36)
    }

    image_paths = []

    print("이미지 생성 시작...")
    img_s = make_solid_bg(IMG_W, IMG_H)
    draw_s = ImageDraw.Draw(img_s)
    draw_s.rectangle([0, 0, IMG_W, 250], fill=BG_HEADER)
    draw_centered(draw_s, "TV-ASAHI FORTUNE", fonts['brand'], 55, TEXT_LIGHT)
    
    # [수정] 타이틀 동적 생성
    m_val = int(date_str[4:6])
    d_val = int(date_str[6:])
    dynamic_title = f"{m_val}/{d_val} 오하아사"
    draw_centered(draw_s, dynamic_title, fonts['title'], 100, TEXT_DARK)
    draw_centered(draw_s, date_display, fonts['date'], 190, TEXT_MID)
    
    COL_RANK_END, COL_ICON_CENTER, COL_SIGN_START = 400, 485, 560
    y_cur, ROW_H = 280, 82
    for item in results:
        rc, rs = rank_color(item['rank']), str(item['rank'])
        center_y = y_cur + (ROW_H // 2)
        r_w = draw_s.textbbox((0, 0), rs, font=fonts['rank_sm'])[2]
        draw_s.text((COL_RANK_END - r_w, center_y - 21), rs, fill=rc, font=fonts['rank_sm'])
        
        s_icon = load_sign_image(item['sign'], 50)
        if s_icon:
            img_s.paste(s_icon, (int(COL_ICON_CENTER - s_icon.width//2), int(center_y - s_icon.height//2 - 3)), s_icon)
            draw_s = ImageDraw.Draw(img_s)
        
        draw_s.text((COL_SIGN_START, center_y - 25), item['sign'], fill=TEXT_DARK, font=fonts['sign_sm'])
        draw_s.line([(180, y_cur + ROW_H), (IMG_W - 180, y_cur + ROW_H)], fill=LINE, width=1)
        y_cur += ROW_H
    
    path_s = os.path.join(output_dir, "00_summary.png")
    img_s.save(path_s); image_paths.append(path_s)

    results_reversed = results[::-1] 
    for i in range(0, len(results_reversed), 2):
        pair = results_reversed[i:i+2]
        img = make_solid_bg(IMG_W, IMG_H)
        draw = ImageDraw.Draw(img)
        draw_centered(draw, f"OHAASA | {date_display}", fonts['brand'], 40, TEXT_LIGHT)
        draw.line([(100, 80), (IMG_W-100, 80)], fill=LINE, width=1)
        
        img = draw_detail_section(img, pair[0], 95, fonts)
        mid_y = IMG_H // 2 
        draw = ImageDraw.Draw(img)
        draw.line([(80, mid_y), (IMG_W-80, mid_y)], fill=LINE, width=1)
        
        if len(pair) > 1:
            img = draw_detail_section(img, pair[1], mid_y + 15, fonts)
            
        draw = ImageDraw.Draw(img)
        draw_centered(draw, "FOR YOUR LUCKY DAY", fonts['brand'], IMG_H - 65, TEXT_LIGHT)
        path_d = os.path.join(output_dir, f"detail_{i//2 + 1}.png")
        img.save(path_d); image_paths.append(path_d)

    public_urls = []
    for p in image_paths:
        url = upload_to_catbox(p)
        if url: public_urls.append(url)
        time.sleep(1)

    if public_urls:
        caption = f"🔮 {date_display} 오늘의 별자리 운세\n\nTV 아사히 '굿모닝'에서 제공하는 오늘의 운세 순위를 확인해보세요!\n\n#오하아사 #오늘의운세 #별자리운세 #운세 #일본운세"

    # OpenCV로 영상 생성 함수
    import subprocess
    def make_video_from_images_cv2(image_paths, video_path):
        if not image_paths:
            print("이미지 없음, 영상 생성 스킵")
            return None
        first_img = cv2.imread(image_paths[0])
        height, width, _ = first_img.shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, 24, (width, height))
        for idx, img_path in enumerate(image_paths):
            duration = 2 if idx == 0 else 4
            frame = cv2.imread(img_path)
            for _ in range(duration * 24):
                out.write(frame)
        out.release()
        print(f"영상 생성 완료: {video_path}")
        return video_path

    # 영상 생성 실행
    video_path = os.path.join(output_dir, f"ohaasa_{date_str}.mp4")
    make_video_from_images_cv2(image_paths, video_path)

    # === 배경음악 합성 (ffmpeg 필요) ===
    import glob
    mp3_files = glob.glob(os.path.join("asset", "mp3", "m*.mp3"))
    if mp3_files:
        bgm_path = random.choice(mp3_files)
        print(f"랜덤 배경음악 선택: {bgm_path}")
        video_with_bgm = os.path.join(output_dir, f"ohaasa_{date_str}_bgm.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            video_with_bgm
        ]
        try:
            subprocess.run(cmd, check=True)
            print(f"배경음악 합성 완료: {video_with_bgm}")
        except Exception as e:
            print(f"ffmpeg 합성 실패: {e}")
        # 릴스 업로드
        caption = f"🔮 {date_str[:4]}.{date_str[4:6]}.{date_str[6:]} 오하아사 별자리 운세\n오늘의 운세 순위를 영상으로 확인하세요! #오하아사 #오늘의운세 #별자리운세 #운세 #릴스"
        success = post_to_instagram_reels(video_with_bgm, caption)
        if success:
            with open("last_upload_weekend.txt", "w") as f:
                f.write(date_str)
            print(f"🎉 {date_str} 릴스 업로드 완료.")
    else:
        print("mp3 파일 없음: asset/mp3/m*.mp3")

    return post_to_instagram(public_urls, caption) if public_urls else False

def main():
    # 한국 시간 기준 계산
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = kst_now.strftime("%Y%m%d")

    # 1. 요일 및 시간 확인 (한국시간 토/일, 오전 5~11시만 실행)
    if kst_now.weekday() not in [5, 6]:
        print(f"오늘은 한국시간 토/일이 아니므로 종료합니다. (요일: {kst_now.weekday()})")
        return
    if not (5 <= kst_now.hour < 10):
        print(f"한국시간 오전 5~10시가 아니므로 종료합니다. (현재: {kst_now.hour}시)")
        return

    # 2. 업로드 여부 확인 (중복 방지)
    tracking_file = "last_upload_weekend.txt"
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            if f.read().strip() == today_str:
                print(f"오늘({today_str})은 이미 주말 운세 업로드가 완료되었습니다.")
                return

    try:
        # 3. 데이터 수집 및 result.json 생성
        data = fetch_and_translate_ohaasa()
        with open("result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # 4. 날짜 일치 확인
        if data['date'] == today_str:
            print(f"날짜 일치 확인 ({today_str}). 프로세스 시작.")
            success = run_full_process(data)
            if success:
                with open(tracking_file, "w") as f:
                    f.write(today_str)
                print("주말 작업 완료 기록 저장.")
        else:
            print(f"데이터 날짜({data['date']})가 오늘({today_str})과 다릅니다. 다음 스케줄에 재시도합니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()