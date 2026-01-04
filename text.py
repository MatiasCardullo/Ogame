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
        if prod <= 0:
            t = cant / (prod*-1 * 3600)
        else:
            t = (cap - cant) / (prod * 3600)
        if t < 1.6:
            return f"{int(t*60)} minutos"
        elif t > 72:
            return f"{int(t/24)} dias"
        else:
            return f"{int(t)} horas"
    except:
        return "—"

def time_str(t, seconds = True):
    d, r = divmod(t, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    d = int(d)
    h = int(h)
    m = int(m)
    s = int(s)
    time = None
    if d > 0:
        parts = [f"{d}d"]
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        time = " ".join(parts)
    else:
        if h > 0:
            time = f"{h}:{m:02d}"
        elif m > 0:
            time = f"{m}"

        if seconds:
            if time:
                time += f":{s:02d}"
            else:
                time = f"{s}"
        elif not time:
            time = "&lt;1m"
    return time
    
def production(prod):
    if abs(prod) > 1:
        prod_t = f"{int(prod)}/s"
    elif abs(prod) > 1/60:
        prod_t = f"{int(prod*60)}/m"
    else:
        prod_t = f"{int(prod*3600)}/h"
    return prod_t

def cantidad(cant):
    if cant > 1000000:
        cant_t = f"{(cant/1000000):.02f}M"
    elif cant > 1000:
        cant_t = f"{(cant/1000):.02f}k"
    else:
        cant_t = f"{int(cant)}"
    return cant_t

def progress_color(i = 0, p1 = 75, p2 = 95, color1 = "#0f0", color2 = "#ff0", color3 = "#f00"):
    return color1 if i < p1 else color2 if i < p2 else color3

def queue_entry(entry, now):
    name = entry.get('name', '')
    start = entry.get('start', now)
    end = entry.get('end', now)
    remaining = max(0, end - now)
    progress = 0
    if end > start:
        progress = min(100, max(0, ((now - start) / (end - start)) * 100))
    return name, remaining, progress

def format_queue_entry(entry, now, seconds):
    """Formato amigable para mostrar una queue"""
    name, remaining, progress = queue_entry(entry, now)
    color = progress_color(progress)
    barra = barra_html(progress, 100, color)
    time = time_str(remaining, seconds)
    aux = f"{name} [{int(progress)}%] ({time})"
    if len(aux) > 35:
        return f"{name}<br>[{int(progress)}%] ({time})<br>{barra}"
    else:
        return f"{aux}<br>{barra}"

def format_research_queue_entry(entry, now, seconds):
    """Formato amigable para mostrar una queue de Investigación"""
    name, remaining, progress = queue_entry(entry, now)
    color = progress_color(progress, 89)
    color = "#0f0" if progress < 89 else "#ff0" if progress < 95 else "#f00"
    barra = barra_html(progress, 100, color, 50)
    return f"{barra} {name} [{progress:.2f}%] ({time_str(remaining, seconds)})"

def planet_production_entry(cant, cap, prodInt, color = "#fff"):
    if cant < cap or prodInt < 0:
        if prodInt > 0:
            full = f"({production(prodInt)}) lleno en {tiempo_lleno(cant, cap, prodInt)}"
        else:
            full = f"({production(prodInt)}) vacio en {tiempo_lleno(cant, cap, prodInt)}"
    else:
        full = f" - almacenes llenos!!!"
    char = progress_color((cant / cap) * 100)
    barra = barra_html(cant, cap, color, 19) + f"<span style='color:{char};'>{'█'}</span>"
    return f"<td>{cantidad(cant)} {full}<br>{barra}"