



def in_rect(x, y, rect):
    sx, sy, ex, ey = rect   # start_x, start_y, end_x, end_y
    return sx <= x <= ex and sy <= y <= ey