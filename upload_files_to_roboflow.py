# 해당 파이썬 파일을 실행시키기 전에 다음 명령어로 파이썬 패키지를 설치하세요.
# pip install tqdm roboflow requests

import os
import sys
import io
import shutil
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from roboflow import Roboflow
from tqdm import tqdm

# [환경 설정] 윈도우 한글 경로 및 출력 문제 방지
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
os.environ["PYTHONUTF8"] = "1"


class RoboflowImageOnlyUploader:
    def __init__(self, root):
        self.root = root
        self.root.title("Roboflow 이미지 전용 업로더")
        self.root.geometry("600x550")

        # --- UI 변수 설정 ---
        self.api_key = tk.StringVar()
        self.ws_id = tk.StringVar()
        self.pj_id = tk.StringVar()
        self.num_workers = tk.IntVar(value=10)  # 병렬 작업 수
        self.limit_count = tk.IntVar(value=500)  # 업로드 제한 수
        self.img_dir = tk.StringVar()

        self.setup_ui()

    def setup_ui(self):
        p = {'padx': 15, 'pady': 8}

        # 1. 접속 정보 섹션
        f1 = tk.LabelFrame(self.root, text="1. Roboflow 접속 정보", padx=10, pady=10)
        f1.pack(fill="x", **p)

        tk.Label(f1, text="Private API Key:").grid(row=0, column=0, sticky="e")
        tk.Entry(f1, textvariable=self.api_key, width=45, show="*").grid(row=0, column=1, padx=10)

        tk.Label(f1, text="Workspace ID:").grid(row=1, column=0, sticky="e")
        tk.Entry(f1, textvariable=self.ws_id, width=45).grid(row=1, column=1, padx=10, pady=5)

        tk.Label(f1, text="Project ID:").grid(row=2, column=0, sticky="e")
        tk.Entry(f1, textvariable=self.pj_id, width=45).grid(row=2, column=1, padx=10)

        # 2. 업로드 설정 섹션
        f2 = tk.LabelFrame(self.root, text="2. 업로드 설정", padx=10, pady=10)
        f2.pack(fill="x", **p)

        tk.Label(f2, text="병렬 작업 수(Workers):").grid(row=0, column=0, sticky="e")
        tk.Entry(f2, textvariable=self.num_workers, width=10).grid(row=0, column=1, sticky="w", padx=10)

        tk.Label(f2, text="업로드 제한(Limit):").grid(row=0, column=2, sticky="e")
        tk.Entry(f2, textvariable=self.limit_count, width=10).grid(row=0, column=3, sticky="w")

        tk.Label(f2, text="이미지 폴더 선택:").grid(row=1, column=0, sticky="e")
        tk.Entry(f2, textvariable=self.img_dir, width=35).grid(row=1, column=1, columnspan=2, padx=10, pady=10)
        tk.Button(f2, text="폴더 찾기", command=lambda: self.img_dir.set(filedialog.askdirectory())).grid(row=1, column=3)

        # 시작 버튼
        tk.Button(self.root, text="🚀 이미지 업로드 시작 (이름순 정렬)", command=self.start_upload,
                  bg="#2196F3", fg="white", font=("Arial", 12, "bold"), height=2).pack(pady=25)

    def start_upload(self):
        # 1. 입력값 확인
        key, ws, pj = self.api_key.get().strip(), self.ws_id.get().strip(), self.pj_id.get().strip()
        img_p = self.img_dir.get()

        if not all([key, ws, pj, img_p]):
            messagebox.showerror("에러", "모든 접속 정보와 이미지 폴더를 입력해주세요.")
            return

        # 2. 로보플로 연결
        try:
            rf = Roboflow(api_key=key)
            project = rf.workspace(ws).project(pj)
        except Exception as e:
            messagebox.showerror("연결 실패", f"Roboflow 접속에 실패했습니다.\n{e}")
            return

        # 3. 이미지 목록 정렬 및 제한 적용
        valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        all_imgs = sorted([f for f in os.listdir(img_p) if f.lower().endswith(valid_exts)])
        targets = all_imgs[:self.limit_count.get()]

        if not targets:
            messagebox.showwarning("알림", "선택한 폴더에 업로드 가능한 이미지 파일이 없습니다.")
            return

        # 4. 임시 폴더 생성 (OpenCV 한글 경로 인식 오류 방지용)
        temp_dir = os.path.join(tempfile.gettempdir(), "rf_img_only_upload")
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        batch_name = f"upload_{datetime.now().strftime('%m%d_%H%M')}"

        if not messagebox.askyesno("확인", f"총 {len(targets)}개의 이미지를 업로드하시겠습니까?"):
            return

        # 5. 병렬 업로드 실행
        success, fail, dup = 0, 0, 0
        with ThreadPoolExecutor(max_workers=self.num_workers.get()) as ex:
            futures = []
            for idx, img in enumerate(targets):
                # 파일을 영문 경로의 임시 이름으로 복사하여 업로드 (한글 경로 문제 해결)
                safe_path = os.path.join(temp_dir, f"img_{idx}{os.path.splitext(img)[1]}")
                shutil.copy2(os.path.join(img_p, img), safe_path)
                futures.append(ex.submit(self.upload_task, project, safe_path, batch_name))

            for f in tqdm(as_completed(futures), total=len(futures), desc="Uploading Images"):
                res = f.result()
                if res == "SUCCESS":
                    success += 1
                elif res == "DUPLICATE":
                    dup += 1
                else:
                    fail += 1

        # 임시 폴더 삭제
        shutil.rmtree(temp_dir, ignore_errors=True)
        messagebox.showinfo("결과", f"성공: {success}\n중복(이미존재): {dup}\n실패: {fail}")

    def upload_task(self, project, img_path, batch):
        try:
            project.upload(img_path, batch_name=batch)
            return "SUCCESS"
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err or "duplicate" in err:
                return "DUPLICATE"
            print(f"업로드 실패: {e}")
            return "FAIL"


if __name__ == "__main__":
    root = tk.Tk()
    app = RoboflowImageOnlyUploader(root)
    root.mainloop()