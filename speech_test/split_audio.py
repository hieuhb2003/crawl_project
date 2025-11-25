import os
import random
from faster_whisper import WhisperModel
from pydub import AudioSegment

# --- CẤU HÌNH ---
MODEL_SIZE = "small"   # Chọn 'tiny', 'base', 'small', 'medium', 'large-v2' (Máy khỏe thì dùng large)
INPUT_FILE = "" # Đường dẫn file audio gốc
OUTPUT_DIR = "dataset_whisper2"

def process_with_whisper():
    print("1. Đang load model Whisper...")
    # Nếu có GPU thì device="cuda", không thì "cpu"
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    print(f"2. Đang Transcribe file: {INPUT_FILE}...")
    segments, info = model.transcribe(INPUT_FILE, beam_size=5)

    # Load audio gốc để tí nữa cắt
    audio = AudioSegment.from_file(INPUT_FILE)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    current_chunk_audio = AudioSegment.empty()
    current_text = ""
    chunk_idx = 1
    
    # Random độ dài mục tiêu ban đầu (20s - 30s)
    current_target_duration = random.uniform(20, 30) * 1000 
    
    print("3. Đang cắt và ghép segment...")
    for segment in segments:
        # segment.start và segment.end là thời gian (giây)
        start_ms = segment.start * 1000
        end_ms = segment.end * 1000
        
        # Cắt đoạn audio tương ứng với câu này
        seg_audio = audio[start_ms:end_ms]
        
        # Cộng dồn vào chunk hiện tại
        current_chunk_audio += seg_audio
        current_text += segment.text + " "
        
        # Kiểm tra độ dài: Nếu >= target random hiện tại thì Xuất file
        if len(current_chunk_audio) >= current_target_duration:
            # Lưu audio
            out_filename = f"chunk_{chunk_idx:04d}.wav"
            out_path = os.path.join(OUTPUT_DIR, out_filename)
            current_chunk_audio.export(out_path, format="wav")
            
            # Lưu text (nếu cần làm data ASR)
            with open(out_path.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
                f.write(current_text.strip())
            
            print(f"-> Saved {out_filename} ({len(current_chunk_audio)/1000:.1f}s / target {current_target_duration/1000:.1f}s): {current_text[:30]}...")
            
            # Reset
            current_chunk_audio = AudioSegment.empty()
            current_text = ""
            chunk_idx += 1
            
            # Random lại target mới cho chunk tiếp theo
            current_target_duration = random.uniform(20, 30) * 1000
            
    # Lưu nốt đoạn thừa cuối cùng (nếu có)
    if len(current_chunk_audio) > 0:
        current_chunk_audio.export(os.path.join(OUTPUT_DIR, f"chunk_{chunk_idx:04d}.wav"), format="wav")

if __name__ == "__main__":
    process_with_whisper()