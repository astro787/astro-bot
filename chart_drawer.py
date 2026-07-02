import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
from astro_calc import SIGN_NAMES, SIGN_EMOJI, get_aspects_with_angles

def draw_natal_chart_pro(natal, city_name='', birth_time=''):
    # Код отрисовки карты (возьми из предыдущего файла)
    # ... (полный код функции)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    return buf
