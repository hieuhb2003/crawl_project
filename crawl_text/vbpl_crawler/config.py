import os

BASE_URL = "https://vbpl.vn"

# Categories to crawl
CATEGORY_URLS = {
    "Văn bản quy phạm pháp luật": "https://vbpl.vn/boquocphong/Pages/vbpq-timkiem.aspx?dvid=314", # Using Search page for main DB
    "Văn bản hợp nhất": "https://vbpl.vn/boquocphong/Pages/vbpq-vanbanhopnhat.aspx?dvid=314",
    "Hệ thống hóa VBQPPL": "https://vbpl.vn/boquocphong/Pages/vbpq-hethonghoa.aspx?dvid=314" # Assuming dvid=314 for consistency, will fallback if needed
}

# NOTE: The URLs above might need adjustment based on actual navigation. 
# For now, we might rely on clicking the links from the home page if direct URLs are complex.
# However, direct URLs are better if stable. 
# Let's use the Home URL and navigation steps if specific URLs are dynamic.
HOME_URL = "https://vbpl.vn/boquocphong/Pages/Home.aspx?dvid=314"

TARGET_AGENCIES = [
    "Quốc hội",
    "Ủy ban thường vụ Quốc hội",
    "Chính phủ",
    "Thủ tướng Chính phủ",
    "Các Bộ, cơ quan ngang Bộ",
    "Các cơ quan khác"
]

TARGET_DOC_TYPES = [
    "Hiến pháp",
    "Bộ luật",
    "Luật",
    "Pháp lệnh",
    "Lệnh",
    "Nghị quyết",
    "Nghị quyết liên tịch",
    "Nghị định",
    "Quyết định",
    "Thông tư",
    "Thông tư liên tịch"
]

OUTPUT_DIR = os.path.join(os.getcwd(), "crawled_data")
