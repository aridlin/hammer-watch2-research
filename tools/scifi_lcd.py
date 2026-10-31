"""Offline LCD styling revision of the full-display Sci-Fi face."""
import argparse
import json
from pathlib import Path
from .scifi_fullscreen import prepare as prepare_fullscreen, coordinate

NAME = 'CWR05G_compassPL03'
COMPASS_CENTER = (345, 112)
PANEL_X = 270
BALANCED_NAME = 'CWR05G_compassPL04'


def restyle(model, balanced=False):
    import copy
    if model['name'] != 'CWR05G_compassPL02':
        raise ValueError('Expected full-screen PL02 model')
    result = copy.deepcopy(model)
    result['name'] = BALANCED_NAME if balanced else NAME
    # Preserve relative coordinates, including the native rotating pointer pivot.
    dx, dy = COMPASS_CENTER[0] - 355, COMPASS_CENTER[1] - 121
    if balanced:
        # Ring bounds (282,48,109,109): 12px to x=270 and y=169.
        dx -= 9
        dy -= 10
    for layer in ('item', 'fade_item'):
        for widget in result[layer]:
            if any(str(value).startswith('Compass_') for value in widget.values()):
                widget['x'] += dx
                widget['y'] += dy
                widget['color'] = '#000000'
    return result


def prepare(source, destination, balanced=False):
    from PIL import Image, ImageDraw
    report = prepare_fullscreen(source, destination)
    firmware = Path(destination) / 'firmware'
    model = restyle(json.loads((firmware / 'dial.json').read_text()), balanced)
    (firmware / 'dial.json').write_text(json.dumps(model, indent=2) + '\n')
    path = firmware / 'background_0_0565.bmp'
    with Image.open(path) as original:
        background = original.convert('RGB')
    # Clear the previous inset compass disk and the divider passing behind it.
    for y in range(181):
        t = y / 465
        color = tuple(round((1-t)*a + t*b) for a,b in zip((188,132,73), (180,123,64)))
        background.paste(color, (PANEL_X, y, 466, y+1))
    draw = ImageDraw.Draw(background)
    draw.line((0, coordinate(120), PANEL_X, coordinate(120)), fill='black', width=2)
    draw.line((coordinate(153), coordinate(120), coordinate(153), coordinate(176)), fill='black', width=2)
    draw.line((PANEL_X, 0, PANEL_X, coordinate(176)), fill='black', width=2)
    draw.line((0, coordinate(176), 465, coordinate(176)), fill='black', width=2)
    background.save(path)
    count = 0
    for path in firmware.rglob('Compass_*_8888.png'):
        with Image.open(path) as original:
            alpha = original.convert('RGBA').getchannel('A')
        image = Image.new('RGBA', alpha.size, (0,0,0,0))
        image.putalpha(alpha)
        image.save(path)
        count += 1
    return {'name': model['name'], 'base_name': 'CWR05G_compassPL01',
            'scale': report['scale'], 'compass_center': [336,102] if balanced else list(COMPASS_CENTER),
            'equal_left_bottom_ring_margins': 12 if balanced else None,
            'compass_theme': 'Black LCD ink on the continuous orange background',
            'compass_images_recolored': count,
            'dividers': 'Battery and ALR/MUTE dividers join the panel boundaries; right panel reaches screen edge',
            'native_bindings_changed': False, 'physical_upload_attempted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--balanced', action='store_true', help='Equal compass margins against left and bottom dividers')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.destination, args.balanced), indent=2))


if __name__ == '__main__':
    main()
