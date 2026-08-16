from strategies.recovery_marubozu.engine.mrcv_core_engine import MRCVEngine

def run_mrcv_bot():
    """Entry point untuk menjalankan MRCV Bot"""
    engine = MRCVEngine()
    engine.run()
