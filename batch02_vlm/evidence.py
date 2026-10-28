"""Local display-only contact sheet of the exact frozen processor observations."""


def save_sheet(frames,source_pts,path):
    from PIL import Image,ImageDraw
    if len(frames)!=10 or len(source_pts)!=10:
        raise ValueError('only the ten frozen observations may be rendered')
    tile_width=384
    tile_height=round(frames.shape[1]*tile_width/frames.shape[2])
    sheet=Image.new('RGB',(tile_width*5,(tile_height+28)*2),'black')
    draw=ImageDraw.Draw(sheet)
    for i,(frame,pts) in enumerate(zip(frames,source_pts)):
        image=Image.fromarray(frame).resize((tile_width,tile_height))
        x=(i%5)*tile_width;y=(i//5)*(tile_height+28)
        sheet.paste(image,(x,y))
        draw.text((x+5,y+tile_height+5),f'observation {i+1}/10 | original PTS {pts:g}s',fill='white')
    sheet.save(path,quality=92)
