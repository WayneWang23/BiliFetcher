import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
import os
import re
import threading
import subprocess
import xml.etree.ElementTree as ET

COOKIE_FILE = "bili_cookie.txt"

# 严格的画质等级映射（QN值）
QUALITY_MAP = {
    "4K 超清": 120,
    "1080P 60帧": 116,
    "1080P 高清": 80,
    "720P 高清": 64,
    "480P 清晰": 32,
    "360P 流畅": 16
}

class BiliUniversalDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("BiliFetcher——B站下载器")
        self.root.geometry("900x850")
        self.root.configure(bg="#f4f4f4")
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        
        self.setup_main_scroll()
        self.load_cookie()

    def setup_main_scroll(self):
        # 创建带滚动条的主布局
        self.canvas = tk.Canvas(self.root, bg="#f4f4f4", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#f4f4f4")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=880)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.setup_ui(self.scrollable_frame)

    def setup_ui(self, parent):
        # 标题
        header = tk.Frame(parent, bg="#fb7299", height=60)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="BiliFetcher B站下载器", font=("微软雅黑", 16, "bold"), fg="white", bg="#fb7299").pack(pady=15)

        # 1. Cookie
        f_cookie = tk.LabelFrame(parent, text=" 1. 账号凭证 (Cookie) ", font=("微软雅黑", 10, "bold"), padx=15, pady=10, bg="#ffffff")
        f_cookie.pack(fill="x", padx=20, pady=5)
        tk.Label(f_cookie, text="💡 获取方式: F12 -> Network -> 刷新 -> 选第一个请求 -> 复制 Cookie 标头", font=("微软雅黑", 9), fg="#666666", bg="#ffffff").pack(anchor="w")
        c_frame = tk.Frame(f_cookie, bg="#ffffff")
        c_frame.pack(fill="x", pady=5)
        self.cookie_text = tk.Text(c_frame, height=4, font=("Consolas", 9), relief="flat", highlightbackground="#dddddd", highlightthickness=1)
        c_sb = ttk.Scrollbar(c_frame, orient="vertical", command=self.cookie_text.yview)
        self.cookie_text.configure(yscrollcommand=c_sb.set)
        self.cookie_text.pack(side="left", fill="x", expand=True)
        c_sb.pack(side="right", fill="y")
        tk.Button(f_cookie, text="💾 保存并暂存凭证", command=self.save_cookie, bg="#fb7299", fg="white", font=("微软雅黑", 9), relief="flat").pack(side=tk.RIGHT, pady=5)

        # 2. 任务列表
        f_url = tk.LabelFrame(parent, text=" 2. 任务列表 (支持 ss/ep/BV/av) ", font=("微软雅黑", 10, "bold"), padx=15, pady=10, bg="#ffffff")
        f_url.pack(fill="x", padx=20, pady=5)
        u_frame = tk.Frame(f_url, bg="#ffffff")
        u_frame.pack(fill="x", pady=5)
        self.url_text = tk.Text(u_frame, height=10, font=("Consolas", 10), relief="flat", highlightbackground="#dddddd", highlightthickness=1)
        u_sb = ttk.Scrollbar(u_frame, orient="vertical", command=self.url_text.yview)
        self.url_text.configure(yscrollcommand=u_sb.set)
        self.url_text.pack(side="left", fill="x", expand=True)
        u_sb.pack(side="right", fill="y")

        # 3. 设置
        f_set = tk.LabelFrame(parent, text=" 3. 下载与弹幕设置 ", font=("微软雅黑", 10, "bold"), padx=15, pady=10, bg="#ffffff")
        f_set.pack(fill="x", padx=20, pady=5)
        tk.Label(f_set, text="画质天花板 (下载其及以下可获取的最高画质):", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.quality_var = tk.StringVar(value="1080P 高清")
        self.quality_combo = ttk.Combobox(f_set, textvariable=self.quality_var, state="readonly", width=12)
        self.quality_combo['values'] = list(QUALITY_MAP.keys())
        self.quality_combo.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        self.download_danmaku_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f_set, text="自动转换 ASS 弹幕", variable=self.download_danmaku_var, bg="#ffffff").grid(row=0, column=2, padx=20)

        dm_frame = tk.Frame(f_set, bg="#ffffff")
        dm_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=10)
        tk.Label(dm_frame, text="字号:", bg="#ffffff").pack(side=tk.LEFT)
        self.dm_size = tk.IntVar(value=70); tk.Entry(dm_frame, textvariable=self.dm_size, width=5).pack(side=tk.LEFT, padx=5)
        tk.Label(dm_frame, text="不透明度:", bg="#ffffff").pack(side=tk.LEFT, padx=10)
        self.dm_opacity = tk.DoubleVar(value=0.25); tk.Entry(dm_frame, textvariable=self.dm_opacity, width=5).pack(side=tk.LEFT, padx=5)
        tk.Label(dm_frame, text="速度系数:", bg="#ffffff").pack(side=tk.LEFT, padx=10)
        self.dm_speed = tk.DoubleVar(value=2.0); tk.Entry(dm_frame, textvariable=self.dm_speed, width=5).pack(side=tk.LEFT, padx=5)
        tk.Label(dm_frame, text="字体:", bg="#ffffff").pack(side=tk.LEFT, padx=10)
        self.dm_font = tk.StringVar(value="Microsoft YaHei"); tk.Entry(dm_frame, textvariable=self.dm_font, width=15).pack(side=tk.LEFT, padx=5)

        # 4. 存储
        f_path = tk.LabelFrame(parent, text=" 4. 存储路径 ", font=("微软雅黑", 10, "bold"), padx=15, pady=10, bg="#ffffff")
        f_path.pack(fill="x", padx=20, pady=5)
        self.path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        tk.Entry(f_path, textvariable=self.path_var, width=65, relief="flat", bg="#f9f9f9").pack(side=tk.LEFT, ipady=3)
        tk.Button(f_path, text=" 选择目录 ", command=lambda: self.path_var.set(filedialog.askdirectory()), font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=10)

        # 状态
        self.status_var = tk.StringVar(value="☕ 等待任务中...")
        tk.Label(parent, textvariable=self.status_var, font=("微软雅黑", 11, "bold"), fg="#fb7299", bg="#f4f4f4", wraplength=800).pack(pady=15)
        self.progress_bar = ttk.Progressbar(parent, length=740, mode='determinate'); self.progress_bar.pack(pady=5)
        self.start_btn = tk.Button(parent, text="🚀 立即开始批量任务", command=self.start_batch_task, bg="#fb7299", fg="white", font=("微软雅黑", 12, "bold"), relief="flat", padx=40, pady=10)
        self.start_btn.pack(pady=20)

    # --- 功能 ---
    def save_cookie(self):
        cookie = self.cookie_text.get("1.0", tk.END).strip()
        with open(COOKIE_FILE, "w", encoding="utf-8") as f: f.write(cookie)
        messagebox.showinfo("成功", "Cookie 已保存")

    def load_cookie(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r", encoding="utf-8") as f: self.cookie_text.insert("1.0", f.read())

    def clean_filename(self, text):
        return re.sub(r'[\\/:*?"<>|]', '_', text)

    def format_time_ass(self, seconds):
        h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
        ms = int((seconds - int(seconds)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{ms:02d}"

    def xml_to_ass_process(self, xml_path, quality_suffix):
        ass_path = os.path.splitext(xml_path)[0].replace("_temp", "") + f"-{quality_suffix}.ass"
        opacity, font_size, speed, font_name = self.dm_opacity.get(), self.dm_size.get(), self.dm_speed.get(), self.dm_font.get()
        alpha_hex = hex(int((1 - opacity) * 255))[2:].zfill(2).upper()
        header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[v4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{font_name},{font_size},&H{alpha_hex}FFFFFF,&H{alpha_hex}FFFFFF,&H{alpha_hex}000000,&H{alpha_hex}000000,0,0,0,0,100,100,0,0,1,1.5,0,2,20,20,20,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
        try:
            tree = ET.parse(xml_path)
            danmakus = []
            row_heights = [i * (font_size + 15) + 60 for i in range(12)]
            for idx, d in enumerate(tree.findall('d')):
                p = d.get('p').split(',')
                start_t, mode = float(p[0]), int(p[1])
                hex_c = hex(int(p[3]))[2:].zfill(6)
                color_bgr = f"{hex_c[4:6]}{hex_c[2:4]}{hex_c[0:2]}"
                if not d.text: continue
                alpha_tag = f"{{\\1a&H{alpha_hex}&\\3a&H{alpha_hex}&\\4a&H{alpha_hex}&\\c&H{color_bgr}&}}"
                y_pos = row_heights[idx % len(row_heights)]
                if mode <= 3:
                    end_t, eff = start_t + (7.0 * speed), f"{{\\move(2000,{y_pos},-600,{y_pos})}}"
                elif mode == 5:
                    end_t, eff = start_t + 4.0, f"{{\\an8\\pos(960,{y_pos})}}"
                elif mode == 4:
                    end_t, eff = start_t + 4.0, f"{{\\an2\\pos(960,{1080 - y_pos})}}"
                else: continue
                danmakus.append(f"Dialogue: 0,{self.format_time_ass(start_t)},{self.format_time_ass(end_t)},Default,,0,0,0,,{eff}{alpha_tag}{d.text}")
            with open(ass_path, "w", encoding="utf-8") as f: f.write(header + "\n".join(danmakus))
            return True
        except: return False

    def start_batch_task(self):
        urls = [u.strip() for u in self.url_text.get("1.0", tk.END).strip().split('\n') if u.strip()]
        if not urls: return
        threading.Thread(target=self.batch_processor, args=(urls,), daemon=True).start()

    def batch_processor(self, urls):
        self.start_btn.config(state=tk.DISABLED)
        cookie, save_base, target_q = self.cookie_text.get("1.0", tk.END).strip(), self.path_var.get(), self.quality_var.get()
        total = len(urls)
        for i, url in enumerate(urls):
            try:
                self.status_var.set(f"[{i+1}/{total}] 🔍 解析元数据...")
                is_pgc = any(x in url for x in ['bangumi', 'ss', 'ep'])
                meta = self.get_pgc_meta(url, cookie) if is_pgc else self.get_ugc_meta(url, cookie)
                if not meta: continue
                id_val, cid, title, ep_name = meta
                cur_title = f"{title} - {ep_name}"
                headers = {"User-Agent": self.ua, "Referer": url, "Cookie": cookie}
                api = f'https://api.bilibili.com/pgc/player/web/playurl?ep_id={id_val}&fnval=16' if is_pgc else f'https://api.bilibili.com/x/player/wbi/playurl?bvid={id_val}&cid={cid}&fnval=16'
                data = requests.get(api, headers=headers).json()
                
                v_url, act_q = self.match_quality(data, target_q)
                a_url = (data.get('result') or data.get('data'))['dash']['audio'][0]['baseUrl']
                
                base_n = self.clean_filename(cur_title)
                final_p = os.path.join(save_base, f"{base_n}-{act_q}.mp4")

                if self.download_danmaku_var.get() and cid:
                    xml_temp = os.path.join(save_base, f"{base_n}_temp.xml")
                    if self.download_xml(cid, xml_temp, url):
                        self.xml_to_ass_process(xml_temp, act_q)
                        if os.path.exists(xml_temp): os.remove(xml_temp)

                v_temp, a_temp = os.path.join(save_base, f"v_{cid}.m4s"), os.path.join(save_base, f"a_{cid}.m4s")
                self.current_prefix = f"[{i+1}/{total}]"
                self.download_file(v_url, v_temp, headers, "视频")
                self.download_file(a_url, a_temp, headers, "音频")
                
                self.status_var.set(f"[{i+1}/{total}] ⚙️ 正在无损合并...")
                subprocess.run(f'ffmpeg -y -i "{v_temp}" -i "{a_temp}" -c copy "{final_p}"', shell=True, capture_output=True)
                if os.path.exists(v_temp): os.remove(v_temp)
                if os.path.exists(a_temp): os.remove(a_temp)
            except Exception as e: print(f"Error: {e}")
        self.status_var.set("✅ 全部任务已完成"); self.start_btn.config(state=tk.NORMAL)
        messagebox.showinfo("任务完成", "批量任务处理完毕！")

    def get_pgc_meta(self, url, cookie):
        ep_m, ss_m = re.search(r'ep(\d+)', url), re.search(r'ss(\d+)', url)
        try:
            p = f"ep_id={ep_m.group(1)}" if ep_m else f"season_id={ss_m.group(1)}"
            res = requests.get(f"https://api.bilibili.com/pgc/view/web/season?{p}", headers={"Cookie": cookie, "User-Agent": self.ua}).json()['result']
            ep = next((e for e in res['episodes'] if str(e['ep_id']) == ep_m.group(1)), res['episodes'][0]) if ep_m else res['episodes'][0]
            return ep['ep_id'], ep['cid'], res['title'], ep['share_copy']
        except: return None

    def get_ugc_meta(self, url, cookie):
        bv_m, av_m = re.search(r'BV([a-zA-Z0-9]+)', url), re.search(r'av(\d+)', url)
        try:
            p = f"bvid={bv_m.group(0)}" if bv_m else f"aid={av_m.group(1)}"
            res = requests.get(f"https://api.bilibili.com/x/web-interface/view?{p}", headers={"Cookie": cookie, "User-Agent": self.ua}).json()['data']
            return res['bvid'], res['cid'], res['title'], res['pages'][0]['part']
        except: return None

    def download_xml(self, cid, path, referer):
        try:
            resp = requests.get(f"https://comment.bilibili.com/{cid}.xml", headers={"User-Agent": self.ua, "Referer": referer}, timeout=10)
            if resp.status_code == 200:
                with open(path, 'wb') as f: f.write(resp.content)
                return True
        except: return False

    def match_quality(self, data, target):
        """天花板过滤算法：仅在目标等级及以下寻找最优解"""
        res = data.get('result') or data.get('data')
        a_desc, a_qn = res['accept_description'], res['accept_quality']
        target_val = QUALITY_MAP.get(target, 80)
        q_dict = dict(zip(a_desc, a_qn))
        
        chosen_qn = None
        chosen_desc = None
        
        # 按 QN 降序排列的描述列表
        for desc, qn in q_dict.items():
            if qn <= target_val: # 只有不高于用户设定的等级才被考虑
                chosen_qn = qn
                chosen_desc = desc
                break # 找到第一个符合条件的（即该范围内最高画质），直接跳出
        
        # 保底
        if not chosen_qn:
            chosen_qn = a_qn[-1]
            chosen_desc = a_desc[-1]
            
        v_url = next((v['baseUrl'] for v in res['dash']['video'] if v['id'] == chosen_qn), res['dash']['video'][0]['baseUrl'])
        return v_url, chosen_desc

    def download_file(self, url, path, headers, label):
        resp = requests.get(url, headers=headers, stream=True)
        total, curr = int(resp.headers.get('Content-Length', 0)), 0
        with open(path, 'ab') as f:
            for chunk in resp.iter_content(65536):
                if chunk:
                    f.write(chunk); curr += len(chunk); p = (curr / total) * 100
                    self.status_var.set(f"{self.current_prefix} 📥 下载{label}: {p:.1f}%")
                    self.progress_bar['value'] = p; self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk(); app = BiliUniversalDownloader(root); root.mainloop()