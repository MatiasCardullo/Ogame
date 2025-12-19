def barra_html(cant, cap, color, size = 20):
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
        t = (cap - cant) / (prod * 3600)
        if t < 1.6:
            return f"{int(t*60)} min."
        elif t >72:
            return f"{int(t/24)} dias"
        else:
            return f"{int(t)} horas"
        
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
        prod_t = f"{int(prod)}/s"
    elif prod > 1/60:
        prod_t = f"{int(prod*60)}/m"
    else:
        prod_t = f"{int(prod*3600)}/h"
    return prod_t

def cantidad(cant):
    if cant > 1000000:
        cant_t = f"{(cant/1000000):.2f}M"
    elif cant > 1000:
        cant_t = f"{(cant/1000):.2f}k"
    else:
        cant_t = f"{int(cant)}"
    return cant_t

def progress_color(i = 0, p1 = 75, p2 = 95, color1 = "#0f0", color2 = "#ff0", color3 = "#f00"):
    return color1 if i < p1 else color2 if i < p2 else color3