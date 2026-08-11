# =====================================================
# database/supabase_storage.py
# Handler untuk upload file ke Supabase Storage
# =====================================================

import os
from database.supabase_client import execute_supabase


def upload_screenshot(local_file_path: str, bucket_name: str, folder_date: str, filename: str) -> tuple[bool, str]:
    """
    Upload file PNG lokal ke Supabase Storage.
    Path di bucket: folder_date / filename
    Contoh: Kamis, 11-06-2026 / BUY_PROFIT_XAUUSD_M1_143000.png
    """
    if not os.path.exists(local_file_path):
        print(f"❌ File tidak ditemukan: {local_file_path}")
        return False, ""

    destination_path = f"{folder_date}/{filename}"

    try:
        def _upload(sb):
            with open(local_file_path, "rb") as f:
                res = sb.storage.from_(bucket_name).upload(
                    path=destination_path,
                    file=f,
                    file_options={"content-type": "image/png"}
                )
                public_url = sb.storage.from_(bucket_name).get_public_url(destination_path)
                return public_url

        public_url = execute_supabase(_upload)
        print(f"✅ Gambar sukses diupload ke Supabase: {destination_path}")
        return True, public_url
    except Exception as e:
        print(f"❌ Gagal upload ke Supabase: {e}")
        return False, ""

