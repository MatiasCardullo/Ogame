import sys, re

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
    d, h, m, s = int(d), int(h), int(m), int(s)
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
                time = f"{s}s"
        else:
            if not time:
                time = "&lt;1m"
            elif h == 0:
                time += "m"
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
        cant_t = f"{(cant/1000000):.3g}M"
    elif cant > 1000:
        cant_t = f"{(cant/1000):.3g}k"
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
        progress = (now - start) / (end - start)
    return name, remaining, progress

def format_queue_entry(entry, now, seconds):
    """Formato amigable para mostrar una queue"""
    name, remaining, progress = queue_entry(entry, now)
    color = progress_color(progress)
    barra = barra_html(progress, 1, color)
    time = time_str(remaining, seconds)
    aux = f"{name} [{progress:.0%}] ({time})"
    if len(aux) > 35:
        return f"{name}<br>[{progress:.0%}] ({time})<br>{barra}"
    else:
        return f"{aux}<br>{barra}"

def format_research_queue_entry(entry, now, seconds):
    """Formato amigable para mostrar una queue de Investigación"""
    name, remaining, progress = queue_entry(entry, now)
    color = progress_color(progress, 89)
    color = "#0f0" if progress < 89 else "#ff0" if progress < 95 else "#f00"
    barra = barra_html(progress, 1, color, 50)
    return f"{barra} {name} [{progress:.2%}] ({time_str(remaining, seconds)})"

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

def draw_box(lines, clear_prev=True):
    """
    Dibuja un rectángulo ASCII con texto y lo actualiza sobre el anterior.
    """
    if not lines:
        return
    # margen derecha e izquierda
    m_d = " " * 3
    m_i = " "
    width = max(len(line) for line in lines)
    height = len(lines) + 2  # bordes arriba y abajo
    if clear_prev:
        # Subir el cursor tantas líneas como ocupó el cuadro anterior
        sys.stdout.write(f"\033[{height}A")
    top = m_i + "┌" + "─" * (width + 2) + "┐" + m_d
    bottom = m_i + "└" + "─" * (width + 2) + "┘" + m_d
    print(top)
    for line in lines:
        print(m_i + f"│ {line.ljust(width)} │" + m_d)
    print(bottom)
    sys.stdout.flush()

def time_str_to_ms(time_str: str) -> int:
    pattern = r'(\d+)\s*(h|m|s)'
    total_ms = 0

    for value, unit in re.findall(pattern, time_str.lower()):
        value = int(value)
        if unit == 'h':
            total_ms += value * 60 * 60 * 1000
        elif unit == 'm':
            total_ms += value * 60 * 1000
        elif unit == 's':
            total_ms += value * 1000

    return total_ms

