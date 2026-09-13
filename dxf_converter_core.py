# -*- coding: utf-8 -*-
"""
柜柜DXF转天工DXF - 核心转换模块 v8
直接操作DXF原始文本，保留所有实体类型和属性
"""

import os
import shutil
import base64
import tempfile

GAP = 40  # 基础间距 mm

# 图形实体类型列表
GRAPHIC_ENTITY_TYPES = {
    'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'ELLIPSE', 'SPLINE',
    'POINT', 'SOLID', 'TRACE', '3DFACE', 'RAY', 'XLINE',
    'TEXT', 'MTEXT', 'ATTDEF', 'ATTRIB',
    'HATCH', 'FILL', 'REGION',
    'INSERT', 'POLYLINE', 'VERTEX', 'SEQEND',
    'DIMENSION', 'LEADER', 'TOLERANCE',
    'IMAGE', 'WIPEOUT',
    'VIEWPORT',
}


def read_dxf_lines(filepath):
    """读取DXF文件为行列表，返回 (lines, eol)"""
    with open(filepath, 'rb') as f:
        raw = f.read()
    is_crlf = b'\r\n' in raw[:1000]
    eol = "\r\n" if is_crlf else "\n"
    text = raw.decode('utf-8', errors='replace')
    lines = text.split(eol)
    return lines, eol


def write_dxf_lines(filepath, lines, eol):
    """写入DXF文件"""
    content = eol.join(lines)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    return os.path.getsize(filepath)


def find_all_entities_sections(lines):
    """找到所有ENTITIES段的起止位置，返回 [(start, end), ...]"""
    sections = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == 'SECTION' and i + 2 < len(lines):
            if lines[i + 2].strip() == 'ENTITIES':
                # 找到SECTION开头的0
                start = i - 1 if i > 0 and lines[i-1].strip() == '0' else i
                # 找ENDSEC
                j = i + 3
                while j < len(lines) and lines[j].strip() != 'ENDSEC':
                    j += 1
                end = j
                sections.append((start, end))
                i = end + 1
                continue
        i += 1
    return sections


def find_entities_section(lines):
    """找到第一个ENTITIES段的起止位置（兼容旧代码）"""
    sections = find_all_entities_sections(lines)
    if sections:
        return sections[0]
    return None, None


def parse_all_entities(lines, sec_start, sec_end):
    """解析ENTITIES段中的所有实体，返回 [(start_idx, end_idx, type), ...]
    end_idx 是下一个实体/ENDSEC 前面的 "0" 的位置（即实体不包含那个"0"）
    """
    entities = []
    i = sec_start
    while i < sec_end:
        if lines[i].strip() == '0' and i + 1 < sec_end:
            etype = lines[i + 1].strip()
            if etype in GRAPHIC_ENTITY_TYPES:
                start = i
                j = i + 2
                found_end = False
                while j < sec_end:
                    if lines[j].strip() == '0':
                        # 检查下一行是什么
                        if j + 1 < sec_end:
                            next_type = lines[j + 1].strip()
                            if next_type in GRAPHIC_ENTITY_TYPES or next_type == 'ENDSEC':
                                found_end = True
                                break
                        elif j + 1 == sec_end:
                            # j+1 正好是 sec_end 位置（ENDSEC）
                            if lines[j + 1].strip() == 'ENDSEC' if j + 1 < len(lines) else False:
                                found_end = True
                                break
                    j += 1
                # 如果没找到结尾，就用sec_end
                if not found_end:
                    j = sec_end
                entities.append((start, j, etype))
                i = j
            else:
                i += 1
        else:
            i += 1
    return entities


def get_entity_layer(lines, ent_start, ent_end):
    """获取实体的图层名"""
    i = ent_start + 2
    while i < ent_end:
        if lines[i].strip() == '8' and i + 1 < ent_end:
            return lines[i + 1].strip()
        i += 2
    return '0'


def is_paper_space_entity(lines, ent_start, ent_end):
    """判断是否为图纸空间实体（67=1）"""
    i = ent_start + 2
    while i < ent_end:
        if lines[i].strip() == '67' and i + 1 < ent_end:
            return lines[i + 1].strip() == '1'
        i += 2
    return False


def copy_entity_lines(lines, ent_start, ent_end):
    """复制实体的所有行"""
    return list(lines[ent_start:ent_end])


def set_entity_layer(entity_lines, layer):
    """设置实体图层"""
    for i in range(0, len(entity_lines) - 1, 2):
        if entity_lines[i].strip() == '8':
            entity_lines[i + 1] = layer
            return


def set_entity_handle(entity_lines, handle):
    """设置实体句柄"""
    for i in range(0, len(entity_lines) - 1, 2):
        if entity_lines[i].strip() == '5':
            entity_lines[i + 1] = handle
            return


def translate_entity(entity_lines, etype, dx, dy):
    """平移实体坐标"""
    if etype == 'LINE':
        _translate_line(entity_lines, dx, dy)
    elif etype == 'ARC':
        _translate_arc(entity_lines, dx, dy)
    elif etype == 'CIRCLE':
        _translate_circle(entity_lines, dx, dy)
    elif etype == 'LWPOLYLINE':
        _translate_lwpolyline(entity_lines, dx, dy)
    elif etype == 'TEXT':
        _translate_text(entity_lines, dx, dy)
    elif etype == 'MTEXT':
        _translate_mtext(entity_lines, dx, dy)
    elif etype == 'POINT':
        _translate_point(entity_lines, dx, dy)
    elif etype == 'ELLIPSE':
        _translate_ellipse(entity_lines, dx, dy)
    elif etype == 'SPLINE':
        _translate_spline(entity_lines, dx, dy)
    elif etype == 'INSERT':
        _translate_insert(entity_lines, dx, dy)
    elif etype == 'SOLID':
        _translate_solid(entity_lines, dx, dy)
    elif etype == '3DFACE':
        _translate_3dface(entity_lines, dx, dy)
    elif etype == 'DIMENSION':
        _translate_dimension(entity_lines, dx, dy)
    elif etype == 'LEADER':
        _translate_leader(entity_lines, dx, dy)
    elif etype == 'HATCH':
        _translate_hatch(entity_lines, dx, dy)
    # 其他类型暂不处理坐标，直接复制（图层会改）


def mirror_entity_x(entity_lines, etype, mirror_x):
    """沿X轴镜像（左右翻转）"""
    if etype == 'LINE':
        _mirror_line_x(entity_lines, mirror_x)
    elif etype == 'ARC':
        _mirror_arc_x(entity_lines, mirror_x)
    elif etype == 'CIRCLE':
        _mirror_circle_x(entity_lines, mirror_x)
    elif etype == 'LWPOLYLINE':
        _mirror_lwpolyline_x(entity_lines, mirror_x)
    elif etype == 'TEXT':
        _mirror_text_x(entity_lines, mirror_x)
    elif etype == 'MTEXT':
        _mirror_mtext_x(entity_lines, mirror_x)
    elif etype == 'POINT':
        _mirror_point_x(entity_lines, mirror_x)
    elif etype == 'ELLIPSE':
        _mirror_ellipse_x(entity_lines, mirror_x)
    elif etype == 'SPLINE':
        _mirror_spline_x(entity_lines, mirror_x)
    elif etype == 'INSERT':
        _mirror_insert_x(entity_lines, mirror_x)
    elif etype == 'SOLID':
        _mirror_solid_x(entity_lines, mirror_x)
    elif etype == '3DFACE':
        _mirror_3dface_x(entity_lines, mirror_x)
    elif etype == 'DIMENSION':
        _mirror_dimension_x(entity_lines, mirror_x)
    elif etype == 'HATCH':
        _mirror_hatch_x(entity_lines, mirror_x)


def _get_field_value(entity_lines, code, default='0'):
    """获取字段值（第一个匹配的），只在偶数索引（组码行）匹配"""
    for i in range(0, len(entity_lines) - 1, 2):
        if entity_lines[i].strip() == code:
            return entity_lines[i + 1].strip()
    return default


def _set_field_value(entity_lines, code, value):
    """设置字段值（第一个匹配的），只在偶数索引（组码行）匹配"""
    for i in range(0, len(entity_lines) - 1, 2):
        if entity_lines[i].strip() == code:
            entity_lines[i + 1] = str(value)
            return True
    return False


def _get_all_field_indices(entity_lines, code):
    """获取所有匹配字段的值索引位置，只在偶数索引（组码行）匹配"""
    indices = []
    for i in range(0, len(entity_lines) - 1, 2):
        if entity_lines[i].strip() == code:
            indices.append(i + 1)
    return indices


def _translate_line(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    x11 = _get_field_value(el, '11', '0')
    y21 = _get_field_value(el, '21', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
        _set_field_value(el, '11', f"{float(x11) + dx:.6f}")
        _set_field_value(el, '21', f"{float(y21) + dy:.6f}")
    except ValueError:
        pass


def _mirror_line_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    x11 = _get_field_value(el, '11', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        _set_field_value(el, '11', f"{mx * 2 - float(x11):.6f}")
    except ValueError:
        pass


def _translate_arc(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
    except ValueError:
        pass


def _mirror_arc_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    sa50 = _get_field_value(el, '50', '0')
    ea51 = _get_field_value(el, '51', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        # 镜像后角度反转
        new_sa = (180 - float(ea51)) % 360
        new_ea = (180 - float(sa50)) % 360
        _set_field_value(el, '50', f"{new_sa:.6f}")
        _set_field_value(el, '51', f"{new_ea:.6f}")
    except ValueError:
        pass


def _translate_circle(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
    except ValueError:
        pass


def _mirror_circle_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
    except ValueError:
        pass


def _translate_lwpolyline(el, dx, dy):
    # LWPOLYLINE有多个10/20组（顶点坐标）
    x_indices = _get_all_field_indices(el, '10')
    y_indices = _get_all_field_indices(el, '20')
    # 按顺序配对
    count = min(len(x_indices), len(y_indices))
    for i in range(count):
        try:
            old_x = float(el[x_indices[i]].strip())
            old_y = float(el[y_indices[i]].strip())
            el[x_indices[i]] = f"{old_x + dx:.6f}"
            el[y_indices[i]] = f"{old_y + dy:.6f}"
        except ValueError:
            pass


def _mirror_lwpolyline_x(el, mx):
    x_indices = _get_all_field_indices(el, '10')
    for idx in x_indices:
        try:
            old_x = float(el[idx].strip())
            el[idx] = f"{mx * 2 - old_x:.6f}"
        except ValueError:
            pass
    # 镜像后顶点顺序反转（保持顺时针/逆时针一致）
    # 找到所有顶点的位置，然后反转向量
    # 简单处理：只反转x坐标，凸度(bulge)取反
    bulge_indices = _get_all_field_indices(el, '42')
    for idx in bulge_indices:
        try:
            old_b = float(el[idx].strip())
            el[idx] = f"{-old_b:.6f}"
        except ValueError:
            pass


def _translate_text(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    x11 = _get_field_value(el, '11', None)
    y21 = _get_field_value(el, '21', None)
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
        if x11 is not None:
            _set_field_value(el, '11', f"{float(x11) + dx:.6f}")
        if y21 is not None:
            _set_field_value(el, '21', f"{float(y21) + dy:.6f}")
    except ValueError:
        pass


def _mirror_text_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    x11 = _get_field_value(el, '11', None)
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        if x11 is not None:
            _set_field_value(el, '11', f"{mx * 2 - float(x11):.6f}")
        # 镜像文字标志 (72组中设置镜像位)
        # 一般不翻转文字，保持可读
    except ValueError:
        pass


def _translate_mtext(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    x11 = _get_field_value(el, '11', None)
    y21 = _get_field_value(el, '21', None)
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
        if x11 is not None:
            _set_field_value(el, '11', f"{float(x11) + dx:.6f}")
        if y21 is not None:
            _set_field_value(el, '21', f"{float(y21) + dy:.6f}")
    except ValueError:
        pass


def _mirror_mtext_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    x11 = _get_field_value(el, '11', None)
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        if x11 is not None:
            _set_field_value(el, '11', f"{mx * 2 - float(x11):.6f}")
    except ValueError:
        pass


def _translate_point(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
    except ValueError:
        pass


def _mirror_point_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
    except ValueError:
        pass


def _translate_ellipse(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    x11 = _get_field_value(el, '11', '0')
    y21 = _get_field_value(el, '21', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
        _set_field_value(el, '11', f"{float(x11) + dx:.6f}")
        _set_field_value(el, '21', f"{float(y21) + dy:.6f}")
    except ValueError:
        pass


def _mirror_ellipse_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    x11 = _get_field_value(el, '11', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        _set_field_value(el, '11', f"{mx * 2 - float(x11):.6f}")
        # 镜像后起始/终止角度也需要调整
        sa = _get_field_value(el, '41', None)
        ea = _get_field_value(el, '42', None)
        if sa is not None and ea is not None:
            new_sa = -float(ea)
            new_ea = -float(sa)
            _set_field_value(el, '41', f"{new_sa:.6f}")
            _set_field_value(el, '42', f"{new_ea:.6f}")
    except ValueError:
        pass


def _translate_spline(el, dx, dy):
    x_indices = _get_all_field_indices(el, '10')
    y_indices = _get_all_field_indices(el, '20')
    count = min(len(x_indices), len(y_indices))
    for i in range(count):
        try:
            old_x = float(el[x_indices[i]].strip())
            old_y = float(el[y_indices[i]].strip())
            el[x_indices[i]] = f"{old_x + dx:.6f}"
            el[y_indices[i]] = f"{old_y + dy:.6f}"
        except ValueError:
            pass


def _mirror_spline_x(el, mx):
    x_indices = _get_all_field_indices(el, '10')
    for idx in x_indices:
        try:
            old_x = float(el[idx].strip())
            el[idx] = f"{mx * 2 - old_x:.6f}"
        except ValueError:
            pass


def _translate_insert(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
    except ValueError:
        pass


def _mirror_insert_x(el, mx):
    x10 = _get_field_value(el, '10', '0')
    try:
        _set_field_value(el, '10', f"{mx * 2 - float(x10):.6f}")
        # X方向缩放取反
        xs = _get_field_value(el, '41', '1')
        _set_field_value(el, '41', f"{-float(xs):.6f}")
    except ValueError:
        pass


def _translate_solid(el, dx, dy):
    for code in ['10', '11', '12', '13']:
        idx = _get_all_field_indices(el, code)
        for i in idx:
            try:
                el[i] = f"{float(el[i].strip()) + dx:.6f}"
            except ValueError:
                pass
    for code in ['20', '21', '22', '23']:
        idx = _get_all_field_indices(el, code)
        for i in idx:
            try:
                el[i] = f"{float(el[i].strip()) + dy:.6f}"
            except ValueError:
                pass


def _mirror_solid_x(el, mx):
    for code in ['10', '11', '12', '13']:
        idx = _get_all_field_indices(el, code)
        for i in idx:
            try:
                el[i] = f"{mx * 2 - float(el[i].strip()):.6f}"
            except ValueError:
                pass


def _translate_3dface(el, dx, dy):
    _translate_solid(el, dx, dy)


def _mirror_3dface_x(el, mx):
    _mirror_solid_x(el, mx)


def _translate_dimension(el, dx, dy):
    x10 = _get_field_value(el, '10', '0')
    y20 = _get_field_value(el, '20', '0')
    x11 = _get_field_value(el, '11', None)
    y21 = _get_field_value(el, '21', None)
    x12 = _get_field_value(el, '12', None)
    y22 = _get_field_value(el, '22', None)
    x13 = _get_field_value(el, '13', None)
    y23 = _get_field_value(el, '23', None)
    x14 = _get_field_value(el, '14', None)
    y24 = _get_field_value(el, '24', None)
    try:
        _set_field_value(el, '10', f"{float(x10) + dx:.6f}")
        _set_field_value(el, '20', f"{float(y20) + dy:.6f}")
        if x11 is not None: _set_field_value(el, '11', f"{float(x11) + dx:.6f}")
        if y21 is not None: _set_field_value(el, '21', f"{float(y21) + dy:.6f}")
        if x12 is not None: _set_field_value(el, '12', f"{float(x12) + dx:.6f}")
        if y22 is not None: _set_field_value(el, '22', f"{float(y22) + dy:.6f}")
        if x13 is not None: _set_field_value(el, '13', f"{float(x13) + dx:.6f}")
        if y23 is not None: _set_field_value(el, '23', f"{float(y23) + dy:.6f}")
        if x14 is not None: _set_field_value(el, '14', f"{float(x14) + dx:.6f}")
        if y24 is not None: _set_field_value(el, '24', f"{float(y24) + dy:.6f}")
    except ValueError:
        pass


def _mirror_dimension_x(el, mx):
    for code in ['10', '11', '12', '13', '14']:
        val = _get_field_value(el, code, None)
        if val is not None:
            try:
                _set_field_value(el, code, f"{mx * 2 - float(val):.6f}")
            except ValueError:
                pass


def _translate_leader(el, dx, dy):
    x_indices = _get_all_field_indices(el, '10')
    y_indices = _get_all_field_indices(el, '20')
    count = min(len(x_indices), len(y_indices))
    for i in range(count):
        try:
            el[x_indices[i]] = f"{float(el[x_indices[i]].strip()) + dx:.6f}"
            el[y_indices[i]] = f"{float(el[y_indices[i]].strip()) + dy:.6f}"
        except ValueError:
            pass


def _translate_hatch(el, dx, dy):
    # HATCH的种子点(10/20)和平移相关的坐标
    x_indices = _get_all_field_indices(el, '10')
    y_indices = _get_all_field_indices(el, '20')
    count = min(len(x_indices), len(y_indices))
    for i in range(count):
        try:
            el[x_indices[i]] = f"{float(el[x_indices[i]].strip()) + dx:.6f}"
            el[y_indices[i]] = f"{float(el[y_indices[i]].strip()) + dy:.6f}"
        except ValueError:
            pass
    # 边界顶点 (11/21)
    x11_indices = _get_all_field_indices(el, '11')
    y21_indices = _get_all_field_indices(el, '21')
    count2 = min(len(x11_indices), len(y21_indices))
    for i in range(count2):
        try:
            el[x11_indices[i]] = f"{float(el[x11_indices[i]].strip()) + dx:.6f}"
            el[y21_indices[i]] = f"{float(el[y21_indices[i]].strip()) + dy:.6f}"
        except ValueError:
            pass


def _mirror_hatch_x(el, mx):
    for code in ['10', '11']:
        indices = _get_all_field_indices(el, code)
        for idx in indices:
            try:
                el[idx] = f"{mx * 2 - float(el[idx].strip()):.6f}"
            except ValueError:
                pass


def get_entity_bbox(entity_lines, etype):
    """计算实体的包围盒，返回 (min_x, max_x, min_y, max_y)"""
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    def update(x, y):
        nonlocal min_x, max_x, min_y, max_y
        if x < min_x: min_x = x
        if x > max_x: max_x = x
        if y < min_y: min_y = y
        if y > max_y: max_y = y
    
    try:
        if etype == 'LINE':
            x10 = float(_get_field_value(entity_lines, '10', '0'))
            y20 = float(_get_field_value(entity_lines, '20', '0'))
            x11 = float(_get_field_value(entity_lines, '11', '0'))
            y21 = float(_get_field_value(entity_lines, '21', '0'))
            update(x10, y20)
            update(x11, y21)
        elif etype == 'ARC':
            cx = float(_get_field_value(entity_lines, '10', '0'))
            cy = float(_get_field_value(entity_lines, '20', '0'))
            r = float(_get_field_value(entity_lines, '40', '0'))
            update(cx - r, cy - r)
            update(cx + r, cy + r)
        elif etype == 'CIRCLE':
            cx = float(_get_field_value(entity_lines, '10', '0'))
            cy = float(_get_field_value(entity_lines, '20', '0'))
            r = float(_get_field_value(entity_lines, '40', '0'))
            update(cx - r, cy - r)
            update(cx + r, cy + r)
        elif etype == 'LWPOLYLINE':
            x_indices = _get_all_field_indices(entity_lines, '10')
            y_indices = _get_all_field_indices(entity_lines, '20')
            count = min(len(x_indices), len(y_indices))
            for i in range(count):
                update(float(entity_lines[x_indices[i]].strip()),
                       float(entity_lines[y_indices[i]].strip()))
        elif etype == 'POINT':
            x10 = float(_get_field_value(entity_lines, '10', '0'))
            y20 = float(_get_field_value(entity_lines, '20', '0'))
            update(x10, y20)
        elif etype == 'TEXT' or etype == 'MTEXT':
            x10 = float(_get_field_value(entity_lines, '10', '0'))
            y20 = float(_get_field_value(entity_lines, '20', '0'))
            update(x10, y20)
        elif etype == 'INSERT':
            x10 = float(_get_field_value(entity_lines, '10', '0'))
            y20 = float(_get_field_value(entity_lines, '20', '0'))
            update(x10, y20)
        elif etype == 'SOLID' or etype == '3DFACE':
            for code_x, code_y in [('10', '20'), ('11', '21'), ('12', '22'), ('13', '23')]:
                vx = _get_field_value(entity_lines, code_x, None)
                vy = _get_field_value(entity_lines, code_y, None)
                if vx and vy:
                    update(float(vx), float(vy))
        elif etype == 'ELLIPSE':
            cx = float(_get_field_value(entity_lines, '10', '0'))
            cy = float(_get_field_value(entity_lines, '20', '0'))
            mx = float(_get_field_value(entity_lines, '11', '0'))
            my = float(_get_field_value(entity_lines, '21', '0'))
            ratio = float(_get_field_value(entity_lines, '40', '1'))
            # 长轴半径
            major_r = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
            minor_r = major_r * ratio
            update(cx - major_r, cy - minor_r)
            update(cx + major_r, cy + minor_r)
        elif etype == 'SPLINE':
            x_indices = _get_all_field_indices(entity_lines, '10')
            y_indices = _get_all_field_indices(entity_lines, '20')
            count = min(len(x_indices), len(y_indices))
            for i in range(count):
                update(float(entity_lines[x_indices[i]].strip()),
                       float(entity_lines[y_indices[i]].strip()))
    except (ValueError, ZeroDivisionError):
        pass
    
    if min_x == float('inf'):
        return None
    return (min_x, max_x, min_y, max_y)


def extract_source_entities(source_path, layer_filter='0'):
    """从源文件提取指定图层的模型空间实体
    返回 (entity_data_list, bbox, eol, all_lines)
    entity_data_list: [(entity_lines, etype), ...]
    """
    lines, eol = read_dxf_lines(source_path)
    all_sections = find_all_entities_sections(lines)
    
    if not all_sections:
        return [], None, eol, lines
    
    # 遍历所有ENTITIES段收集实体
    filtered = []
    bbox = None
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    for sec_start, sec_end in all_sections:
        section_entities = parse_all_entities(lines, sec_start, sec_end)
        
        for s, e, t in section_entities:
            if is_paper_space_entity(lines, s, e):
                continue
            layer = get_entity_layer(lines, s, e)
            if layer_filter and layer != layer_filter:
                continue
            # 跳过一些非图形辅助实体
            if t in ('SEQEND',):
                continue
            
            ent_lines = copy_entity_lines(lines, s, e)
            filtered.append((ent_lines, t))
            
            # 计算bbox
            eb = get_entity_bbox(ent_lines, t)
            if eb:
                eminx, emaxx, eminy, emaxy = eb
                if eminx < min_x: min_x = eminx
                if emaxx > max_x: max_x = emaxx
                if eminy < min_y: min_y = eminy
                if emaxy > max_y: max_y = emaxy
    
    if min_x != float('inf'):
        bbox = {
            "min_x": min_x, "max_x": max_x,
            "min_y": min_y, "max_y": max_y,
            "width": max(max_x - min_x, 0.001),
            "height": max(max_y - min_y, 0.001),
        }
    
    return filtered, bbox, eol, lines


def extract_all_layer_entities(source_path):
    """从源文件提取所有图层的模型空间实体，按图层分组
    返回 {layer: {'entities': [(ent_lines, etype), ...], 'bbox': {...}}}
    """
    lines, eol = read_dxf_lines(source_path)
    all_sections = find_all_entities_sections(lines)
    
    if not all_sections:
        return {}, eol, lines
    
    layers = {}
    
    for sec_start, sec_end in all_sections:
        section_entities = parse_all_entities(lines, sec_start, sec_end)
        
        for s, e, t in section_entities:
            if is_paper_space_entity(lines, s, e):
                continue
            layer = get_entity_layer(lines, s, e)
            if t in ('SEQEND',):
                continue
            
            ent_lines = copy_entity_lines(lines, s, e)
            
            if layer not in layers:
                layers[layer] = {
                    'entities': [],
                    'min_x': float('inf'), 'max_x': float('-inf'),
                    'min_y': float('inf'), 'max_y': float('-inf'),
                }
            
            layers[layer]['entities'].append((ent_lines, t))
            
            eb = get_entity_bbox(ent_lines, t)
            if eb:
                eminx, emaxx, eminy, emaxy = eb
                if eminx < layers[layer]['min_x']: layers[layer]['min_x'] = eminx
                if emaxx > layers[layer]['max_x']: layers[layer]['max_x'] = emaxx
                if eminy < layers[layer]['min_y']: layers[layer]['min_y'] = eminy
                if emaxy > layers[layer]['max_y']: layers[layer]['max_y'] = emaxy
    
    # 计算每个图层的bbox
    for layer in layers:
        d = layers[layer]
        if d['min_x'] != float('inf'):
            d['bbox'] = {
                'min_x': d['min_x'], 'max_x': d['max_x'],
                'min_y': d['min_y'], 'max_y': d['max_y'],
                'width': max(d['max_x'] - d['min_x'], 0.001),
                'height': max(d['max_y'] - d['min_y'], 0.001),
            }
        else:
            d['bbox'] = None
    
    return layers, eol, lines


def build_view_entities(source_entities, source_bbox, thickness, text_content):
    """生成六视图的所有实体
    返回 [(entity_lines, etype, layer), ...]
    """
    result = []
    W = source_bbox["width"]
    H = source_bbox["height"]
    T = thickness
    
    dx = -source_bbox["min_x"]
    dy = -source_bbox["min_y"]
    
    handle_counter = 100
    
    def next_handle():
        nonlocal handle_counter
        handle_counter += 1
        return format(handle_counter + 500, 'X')
    
    # 主视图的虚拟最小外接框左下角在坐标原点(0,0)
    # 侧视图环绕主视图四周：左-40mm，右+40mm，下-40mm，上+40mm
    # 镜像视图在最右侧
    
    # 1. 主视图（图层0）- 左下角(0,0)
    for ent_lines, etype in source_entities:
        el = list(ent_lines)  # 复制
        translate_entity(el, etype, dx, dy)
        set_entity_layer(el, "0")
        set_entity_handle(el, next_handle())
        result.append((el, etype, "0"))
    
    # 2. 最右侧镜像视图（图层1）
    right_view_right = W + GAP + T
    mirror_left = right_view_right + GAP
    # 镜像轴 = 源中心和目标中心的中点
    source_center_x = W / 2
    target_center_x = mirror_left + W / 2
    mirror_axis = (source_center_x + target_center_x) / 2
    
    for ent_lines, etype in source_entities:
        el = list(ent_lines)
        translate_entity(el, etype, dx, dy)
        mirror_entity_x(el, etype, mirror_axis)
        set_entity_layer(el, "1")
        set_entity_handle(el, next_handle())
        result.append((el, etype, "1"))
    
    # 提取源实体中的孔位（CIRCLE）用于侧视图投影
    circle_holes = []  # [(cx, cy, r), ...]  归一化坐标
    for ent_lines, etype in source_entities:
        if etype == 'CIRCLE':
            cx = float(_get_field_value(ent_lines, '10', '0')) + dx
            cy = float(_get_field_value(ent_lines, '20', '0')) + dy
            r = float(_get_field_value(ent_lines, '40', '0'))
            circle_holes.append((cx, cy, r))
    
    # 提取LWPOLYLINE拉槽用于侧视图投影（近似用边界框）
    slot_rects = []  # [(min_x, min_y, max_x, max_y), ...]  归一化坐标
    for ent_lines, etype in source_entities:
        if etype == 'LWPOLYLINE':
            x_indices = _get_all_field_indices(ent_lines, '10')
            y_indices = _get_all_field_indices(ent_lines, '20')
            xs = [float(ent_lines[i]) + dx for i in x_indices]
            ys = [float(ent_lines[i]) + dy for i in y_indices]
            if xs and ys:
                slot_rects.append((min(xs), min(ys), max(xs), max(ys)))
    
    # 3. 左视图厚度矩形（图层2）- 主视图左侧40mm
    left_x2 = -GAP
    left_x1 = -GAP - T
    rect_lines = _make_rect_lines(left_x1, 0, left_x2, H, "2", next_handle)
    result.extend(rect_lines)
    # 左视图孔位投影：圆孔 → 两条横线（Y方向），横贯厚度
    for cx, cy, r in circle_holes:
        y_top = cy + r
        y_bot = cy - r
        line1 = _make_line_entity(left_x1, y_top, left_x2, y_top, "2", next_handle)
        line2 = _make_line_entity(left_x1, y_bot, left_x2, y_bot, "2", next_handle)
        result.append(line1)
        result.append(line2)
    # 拉槽投影：用边界框的上下边
    for sx1, sy1, sx2, sy2 in slot_rects:
        line1 = _make_line_entity(left_x1, sy2, left_x2, sy2, "2", next_handle)
        line2 = _make_line_entity(left_x1, sy1, left_x2, sy1, "2", next_handle)
        result.append(line1)
        result.append(line2)
    
    # 4. 右视图厚度矩形（图层3）- 主视图右侧40mm
    right_x1 = W + GAP
    right_x2 = W + GAP + T
    rect_lines = _make_rect_lines(right_x1, 0, right_x2, H, "3", next_handle)
    result.extend(rect_lines)
    # 右视图孔位投影
    for cx, cy, r in circle_holes:
        y_top = cy + r
        y_bot = cy - r
        line1 = _make_line_entity(right_x1, y_top, right_x2, y_top, "3", next_handle)
        line2 = _make_line_entity(right_x1, y_bot, right_x2, y_bot, "3", next_handle)
        result.append(line1)
        result.append(line2)
    # 拉槽投影
    for sx1, sy1, sx2, sy2 in slot_rects:
        line1 = _make_line_entity(right_x1, sy2, right_x2, sy2, "3", next_handle)
        line2 = _make_line_entity(right_x1, sy1, right_x2, sy1, "3", next_handle)
        result.append(line1)
        result.append(line2)
    
    # 5. 下视图厚度矩形（图层4）- 主视图下侧40mm
    bottom_y2 = -GAP
    bottom_y1 = -GAP - T
    rect_lines = _make_rect_lines(0, bottom_y1, W, bottom_y2, "4", next_handle)
    result.extend(rect_lines)
    # 下视图孔位投影：圆孔 → 两条竖线（X方向），贯穿厚度
    for cx, cy, r in circle_holes:
        x_left = cx - r
        x_right = cx + r
        line1 = _make_line_entity(x_left, bottom_y1, x_left, bottom_y2, "4", next_handle)
        line2 = _make_line_entity(x_right, bottom_y1, x_right, bottom_y2, "4", next_handle)
        result.append(line1)
        result.append(line2)
    # 拉槽投影：用边界框的左右边
    for sx1, sy1, sx2, sy2 in slot_rects:
        line1 = _make_line_entity(sx1, bottom_y1, sx1, bottom_y2, "4", next_handle)
        line2 = _make_line_entity(sx2, bottom_y1, sx2, bottom_y2, "4", next_handle)
        result.append(line1)
        result.append(line2)
    
    # 6. 上视图厚度矩形（图层5）- 主视图上侧40mm
    top_y1 = H + GAP
    top_y2 = H + GAP + T
    rect_lines = _make_rect_lines(0, top_y1, W, top_y2, "5", next_handle)
    result.extend(rect_lines)
    # 上视图孔位投影
    for cx, cy, r in circle_holes:
        x_left = cx - r
        x_right = cx + r
        line1 = _make_line_entity(x_left, top_y1, x_left, top_y2, "5", next_handle)
        line2 = _make_line_entity(x_right, top_y1, x_right, top_y2, "5", next_handle)
        result.append(line1)
        result.append(line2)
    # 拉槽投影
    for sx1, sy1, sx2, sy2 in slot_rects:
        line1 = _make_line_entity(sx1, top_y1, sx1, top_y2, "5", next_handle)
        line2 = _make_line_entity(sx2, top_y1, sx2, top_y2, "5", next_handle)
        result.append(line1)
        result.append(line2)
    
    # 7. 文字层（TextToNest）
    text_y = bottom_y1 - 20
    text = text_content or "output"
    text_ent = _make_text_entity(0, text_y, text, 3.0, "TextToNest", next_handle)
    result.append(text_ent)
    
    return result


def _make_line_entity(x1, y1, x2, y2, layer, handle_func):
    """创建一个LINE实体"""
    lines = [
        "0", "LINE",
        "5", handle_func(),
        "8", layer,
        "10", f"{x1:.6f}",
        "20", f"{y1:.6f}",
        "30", "0.000000",
        "11", f"{x2:.6f}",
        "21", f"{y2:.6f}",
        "31", "0.000000",
    ]
    return (lines, "LINE", layer)


def _make_rect_lines(x1, y1, x2, y2, layer, handle_func):
    """创建矩形的四条边"""
    return [
        _make_line_entity(x1, y1, x2, y1, layer, handle_func),
        _make_line_entity(x2, y1, x2, y2, layer, handle_func),
        _make_line_entity(x2, y2, x1, y2, layer, handle_func),
        _make_line_entity(x1, y2, x1, y1, layer, handle_func),
    ]


def _make_text_entity(x, y, text, height, layer, handle_func):
    """创建一个TEXT实体"""
    lines = [
        "0", "TEXT",
        "5", handle_func(),
        "8", layer,
        "10", f"{x:.6f}",
        "20", f"{y:.6f}",
        "30", "0.000000",
        "40", f"{height:.6f}",
        "1", text,
        "7", "Standard",
        "72", "0",
        "73", "0",
        "11", f"{x:.6f}",
        "21", f"{y:.6f}",
        "31", "0.000000",
    ]
    return (lines, "TEXT", layer)


def write_to_template(template_path, output_path, view_entities):
    """将视图实体写入模板文件，替换模型空间实体"""
    lines, eol = read_dxf_lines(template_path)
    sec_start, sec_end = find_entities_section(lines)
    
    if sec_start is None:
        raise Exception("模板文件中未找到ENTITIES段")
    
    all_entities = parse_all_entities(lines, sec_start, sec_end)
    
    # 找到模型空间实体的范围（非图纸空间的图形实体）
    ms_entities = []
    for s, e, t in all_entities:
        if not is_paper_space_entity(lines, s, e) and t in GRAPHIC_ENTITY_TYPES:
            ms_entities.append((s, e, t))
    
    if not ms_entities:
        raise Exception("模板文件中未找到模型空间实体")
    
    ms_start = ms_entities[0][0]
    ms_end = ms_entities[-1][1]
    
    # 构建新实体的行
    new_entity_lines = []
    for ent_lines, etype, layer in view_entities:
        new_entity_lines.extend(ent_lines)
    
    # 替换
    new_section_lines = (
        lines[sec_start:ms_start] +
        new_entity_lines +
        lines[ms_end:sec_end]
    )
    
    new_all_lines = (
        lines[:sec_start] +
        new_section_lines +
        lines[sec_end:]
    )
    
    # 更新EXTENTS
    _update_extents(new_all_lines, view_entities)
    
    size = write_dxf_lines(output_path, new_all_lines, eol)
    return size


def _update_extents(lines, entities):
    """更新HEADER段中的EXTMIN/EXTMAX"""
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    for ent_lines, etype, layer in entities:
        eb = get_entity_bbox(ent_lines, etype)
        if eb:
            eminx, emaxx, eminy, emaxy = eb
            if eminx < min_x: min_x = eminx
            if emaxx > max_x: max_x = emaxx
            if eminy < min_y: min_y = eminy
            if emaxy > max_y: max_y = emaxy
    
    if min_x == float('inf'):
        return
    
    padding = 10
    min_x -= padding
    min_y -= padding
    max_x += padding
    max_y += padding
    
    # 查找并更新EXTMIN/EXTMAX
    in_header = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == 'SECTION' and i + 2 < len(lines):
            if lines[i + 2].strip() == 'HEADER':
                in_header = True
        elif stripped == 'ENDSEC':
            if in_header:
                break
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '$EXTMIN' and i + 4 < len(lines):
            # EXTMIN 后面跟着 10/x 20/y
            j = i + 1
            if lines[j].strip() == '10':
                lines[j + 1] = f"{min_x:.6f}"
            # 找20
            for k in range(j, min(j + 20, len(lines))):
                if lines[k].strip() == '20':
                    lines[k + 1] = f"{min_y:.6f}"
                    break
        elif stripped == '$EXTMAX' and i + 4 < len(lines):
            j = i + 1
            if lines[j].strip() == '10':
                lines[j + 1] = f"{max_x:.6f}"
            for k in range(j, min(j + 20, len(lines))):
                if lines[k].strip() == '20':
                    lines[k + 1] = f"{max_y:.6f}"
                    break


def convert_single(source_path, template_path, output_path, thickness, source_layer, text_content):
    """转换单个文件，返回 (success, message)"""
    try:
        # 1. 提取源文件所有图层的实体
        all_layers, eol, src_lines = extract_all_layer_entities(source_path)
        
        # 检查是否有完整的六个视图图层（0-5）
        has_all_views = all(str(l) in all_layers for l in range(6))
        
        if has_all_views:
            # 源文件已有完整六视图，直接重新排布
            view_entities = _rebuild_from_all_layers(all_layers, thickness, text_content)
            src_count = sum(len(all_layers[str(l)]['entities']) for l in range(6) if str(l) in all_layers)
        else:
            # 只有主视图，用旧逻辑生成六视图
            if source_layer not in all_layers:
                return False, f"未找到图层{source_layer}的图形实体"
            source_data = all_layers[source_layer]
            source_entities = source_data['entities']
            bbox = source_data['bbox']
            if not bbox:
                return False, "无法计算图形边界"
            view_entities = build_view_entities(source_entities, bbox, thickness, text_content)
            src_count = len(source_entities)
        
        # 2. 写入模板
        size = write_to_template(template_path, output_path, view_entities)
        
        return True, f"成功 ({src_count}个源实体, {len(view_entities)}个视图实体, {size:,}字节)"
    
    except Exception as e:
        import traceback
        return False, f"失败: {str(e)}\n{traceback.format_exc()}"


def _rebuild_from_all_layers(all_layers, thickness, text_content):
    """源文件已有六个视图图层，重新排布位置
    主视图(图层0)左下角在原点，侧视图环绕四周，间距40mm
    """
    result = []
    handle_counter = 100
    
    def next_handle():
        nonlocal handle_counter
        handle_counter += 1
        return format(handle_counter + 500, 'X')
    
    # 主视图（图层0）- 左下角(0,0)
    main_data = all_layers.get('0', all_layers.get(0, None))
    if not main_data or not main_data['bbox']:
        return build_view_entities(
            all_layers.get('0', {}).get('entities', []),
            all_layers.get('0', {}).get('bbox', {'min_x':0,'max_x':100,'min_y':0,'max_y':100,'width':100,'height':100}),
            thickness, text_content
        )
    
    main_bbox = main_data['bbox']
    W = main_bbox['width']
    H = main_bbox['height']
    T = thickness
    GAP = 40.0
    
    dx_main = -main_bbox['min_x']
    dy_main = -main_bbox['min_y']
    
    # 1. 主视图（图层0）
    for ent_lines, etype in main_data['entities']:
        el = list(ent_lines)
        translate_entity(el, etype, dx_main, dy_main)
        set_entity_layer(el, "0")
        set_entity_handle(el, next_handle())
        result.append((el, etype, "0"))
    
    # 2. 仰视图/反面视图（图层1）- 最右侧
    # 位置：右视图右侧40mm处
    right_view_right = W + GAP + T
    mirror_left = right_view_right + GAP
    
    layer1_data = all_layers.get('1', all_layers.get(1, None))
    if layer1_data and layer1_data['bbox']:
        l1_bbox = layer1_data['bbox']
        # 整体平移：左下角对齐到 (mirror_left, 0)
        dx1 = mirror_left - l1_bbox['min_x']
        dy1 = 0 - l1_bbox['min_y']
        for ent_lines, etype in layer1_data['entities']:
            el = list(ent_lines)
            translate_entity(el, etype, dx1, dy1)
            set_entity_layer(el, "1")
            set_entity_handle(el, next_handle())
            result.append((el, etype, "1"))
    
    # 3. 左视图（图层2）- 主视图左侧40mm
    layer2_data = all_layers.get('2', all_layers.get(2, None))
    left_x2 = -GAP
    left_x1 = -GAP - T
    if layer2_data and layer2_data['entities']:
        l2_bbox = layer2_data['bbox']
        # 整体平移到正确位置
        dx2 = left_x1 - l2_bbox['min_x']
        dy2 = 0 - l2_bbox['min_y']
        for ent_lines, etype in layer2_data['entities']:
            el = list(ent_lines)
            translate_entity(el, etype, dx2, dy2)
            set_entity_layer(el, "2")
            set_entity_handle(el, next_handle())
            result.append((el, etype, "2"))
    else:
        # 没有就画矩形
        rect_lines = _make_rect_lines(left_x1, 0, left_x2, H, "2", next_handle)
        result.extend(rect_lines)
    
    # 4. 右视图（图层3）- 主视图右侧40mm
    layer3_data = all_layers.get('3', all_layers.get(3, None))
    right_x1 = W + GAP
    right_x2 = W + GAP + T
    if layer3_data and layer3_data['entities']:
        l3_bbox = layer3_data['bbox']
        dx3 = right_x1 - l3_bbox['min_x']
        dy3 = 0 - l3_bbox['min_y']
        for ent_lines, etype in layer3_data['entities']:
            el = list(ent_lines)
            translate_entity(el, etype, dx3, dy3)
            set_entity_layer(el, "3")
            set_entity_handle(el, next_handle())
            result.append((el, etype, "3"))
    else:
        rect_lines = _make_rect_lines(right_x1, 0, right_x2, H, "3", next_handle)
        result.extend(rect_lines)
    
    # 5. 下视图（图层4）- 主视图下侧40mm
    layer4_data = all_layers.get('4', all_layers.get(4, None))
    bottom_y2 = -GAP
    bottom_y1 = -GAP - T
    if layer4_data and layer4_data['entities']:
        l4_bbox = layer4_data['bbox']
        dx4 = 0 - l4_bbox['min_x']
        dy4 = bottom_y1 - l4_bbox['min_y']
        for ent_lines, etype in layer4_data['entities']:
            el = list(ent_lines)
            translate_entity(el, etype, dx4, dy4)
            set_entity_layer(el, "4")
            set_entity_handle(el, next_handle())
            result.append((el, etype, "4"))
    else:
        rect_lines = _make_rect_lines(0, bottom_y1, W, bottom_y2, "4", next_handle)
        result.extend(rect_lines)
    
    # 6. 上视图（图层5）- 主视图上侧40mm
    layer5_data = all_layers.get('5', all_layers.get(5, None))
    top_y1 = H + GAP
    top_y2 = H + GAP + T
    if layer5_data and layer5_data['entities']:
        l5_bbox = layer5_data['bbox']
        dx5 = 0 - l5_bbox['min_x']
        dy5 = top_y1 - l5_bbox['min_y']
        for ent_lines, etype in layer5_data['entities']:
            el = list(ent_lines)
            translate_entity(el, etype, dx5, dy5)
            set_entity_layer(el, "5")
            set_entity_handle(el, next_handle())
            result.append((el, etype, "5"))
    else:
        rect_lines = _make_rect_lines(0, top_y1, W, top_y2, "5", next_handle)
        result.extend(rect_lines)
    
    # 7. 文字层
    text_y = bottom_y1 - 20
    text = text_content or "output"
    text_ent = _make_text_entity(0, text_y, text, 3.0, "TextToNest", next_handle)
    result.append(text_ent)
    
    return result
