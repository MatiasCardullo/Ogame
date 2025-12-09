def barra_html(cant, cap, color, size=20):
    try:
        if cap <= 0:
            return ""
        ratio = min(1, cant / cap)
        filled = int(size * ratio)
        empty = size - filled
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

def time_str(t):
    d, r = divmod(t, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    d = int(d)
    h = int(h)
    m = int(m)
    s = int(s)
    if d > 0:
        parts = [f"{d}d"]
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        time = " ".join(parts)
    else:
        if h > 0:
            time = f"{h}:{m:02d}:{s:02d}"
        elif m > 0:
            time = f"{m}:{s:02d}"
        else:
            time = f"{s}s"
    return time
    
def produccion(prod):
    if prod > 1:
        prod_t = f"{prod:+.2f}/s"
    elif prod > 1/60:
        prod_t = f"{prod*60:+.2f}/m"
    else:
        prod_t = f"{prod*3600:+.2f}/h"
    return prod_t

def cantidad(cant):
    if cant > 1000000:
        cant_t = f"{(cant/1000000):.2f}M"
    elif cant > 1000:
        cant_t = f"{(cant/1000):.2f}k"
    else:
        cant_t = f"{cant}"
    return cant_t