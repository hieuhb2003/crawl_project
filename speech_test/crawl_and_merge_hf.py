import os
from datasets import load_dataset, concatenate_datasets, Audio, Dataset
import warnings

# Tắt warning cho đỡ rối mắt
warnings.filterwarnings("ignore")

# Danh sách dataset
DATASETS = [
    "doof-ferb/vlsp2020_vinai_100h",
    "doof-ferb/VietMed_unlabeled",
    "doof-ferb/VietMDD",
    "doof-ferb/fpt_fosd",
    "doof-ferb/vais1000",
    "doof-ferb/Vietnam-Celeb",
    "doof-ferb/ViCocktail",
    "doof-ferb/infore1_25hours",
    "doof-ferb/gigaspeech2_vie",
    "doof-ferb/VietMed_labeled",
    "doof-ferb/BibleMMS_vie",
    "doof-ferb/Speech-MASSIVE_vie"
]

# Các tên cột text có thể xuất hiện
TEXT_COLUMNS = ['transcription', 'text', 'sentence']
OUTPUT_DIR = "merged_dataset"

def process_datasets():
    all_datasets = []
    
    print(f"=== BẮT ĐẦU TỔNG HỢP {len(DATASETS)} DATASET ===\n")
    
    for repo_id in DATASETS:
        print(f"-> Đang xử lý: {repo_id}")
        
        # Thử các split phổ biến
        for split in ['train', 'test', 'validation', 'other']:
            try:
                # Load dataset ở chế độ streaming=False để tải về máy
                # Nếu muốn tiết kiệm ổ cứng có thể dùng streaming=True nhưng sẽ chậm khi xử lý
                ds = load_dataset(repo_id, split=split)
                
                # 1. Tìm cột text
                found_text_col = None
                for col in TEXT_COLUMNS:
                    if col in ds.column_names:
                        found_text_col = col
                        break
                
                if not found_text_col:
                    print(f"   [SKIP] Split '{split}': Không tìm thấy cột text nào trong {ds.column_names}")
                    continue
                
                # 2. Chuẩn hóa cột
                # Rename cột text tìm được thành 'transcription'
                if found_text_col != 'transcription':
                    ds = ds.rename_column(found_text_col, 'transcription')
                
                # Giữ lại đúng 2 cột: audio, transcription
                columns_to_keep = ['audio', 'transcription']
                columns_to_remove = [c for c in ds.column_names if c not in columns_to_keep]
                ds = ds.remove_columns(columns_to_remove)
                
                # 3. Cast Audio về cùng sample rate (ví dụ 16kHz) để merge được
                ds = ds.cast_column("audio", Audio(sampling_rate=16000))
                
                print(f"   [OK] Split '{split}': {len(ds)} mẫu")
                all_datasets.append(ds)
                
            except Exception as e:
                # Lỗi thường gặp là split không tồn tại, bỏ qua
                pass

    if not all_datasets:
        print("\n[ERROR] Không tải được dataset nào!")
        return

    print(f"\n=== ĐANG MERGE {len(all_datasets)} DATASET CON ===")
    # Merge tất cả lại
    final_dataset = concatenate_datasets(all_datasets)
    
    print(f"Tổng số mẫu dữ liệu: {len(final_dataset)}")
    print("Ví dụ mẫu đầu tiên:")
    print(final_dataset[0])
    
    print(f"\n=== ĐANG LƯU DATASET XUỐNG {OUTPUT_DIR} ===")
    final_dataset.save_to_disk(OUTPUT_DIR)
    print("[DONE] Hoàn tất!")

if __name__ == "__main__":
    process_datasets()
