def barra(cant, cap, color):
    try:
        if cap <= 0:
            return ""
        ratio = min(1, cant / cap)
        filled = int(20 * ratio)
        empty = 20 - filled
        return f"<span style='color:{color};'>{'█'*filled}</span>" \
                f"<span style='color:#444;'>{'░'*empty}</span>"
    except:
        return ""

def tiempo_lleno(cant, cap, prod):
    try:
        if prod <= 0 or cant >= cap:
            return "—"
        horas = (cap - cant) / (prod * 3600)
        if horas < 1:
            return f"{horas*60:.1f}m"
        return f"{horas:.1f}h"
    except:
        return "—"
    
def produccion(prod):
    if prod > 1:
        prod_t = f"{prod:+.2f}/s"
    elif prod > 1/60:
        prod_t = f"{prod*60:+.2f}/m"
    else:
        prod_t = f"{prod*3600:+.2f}/h"
    return prod_t