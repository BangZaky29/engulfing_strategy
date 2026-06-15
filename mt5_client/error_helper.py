import MetaTrader5 as mt5


def get_last_error() -> str:
    try:
        err = mt5.last_error()
        if err is not None:
            return str(err)
        return "No error details available"
    except AttributeError:
        return "last_error attribute not found in MetaTrader5 module"
    except Exception as e:
        return f"Gagal mengambil last_error: {e}"
