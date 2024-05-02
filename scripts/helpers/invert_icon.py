def invert_ico(icon_path: Path):
    from PIL import Image
    image = Image.open(icon_path)
    assert image.mode == "LA", 'This function converts an image with mode "LA"'

    def invert_la(img):
        inverted_pixels = [(255 - pixel[0], pixel[1]) for pixel in img.getdata()]
        inverted_img = Image.new(img.mode, img.size)
        inverted_img.putdata(inverted_pixels)
        return inverted_img

    output_path = f"{icon_path.stem}_inv{icon_path.suffix}"

    inverted_image = invert_la(image)
    inverted_image.save(output_path, format='ICO', sizes=[image.size])



if __name__ == '__main__':
    from pathlib import Path
    icon_path = Path("res/images/icon.ico")
    invert_ico(icon_path)
    print(f"Inverted icon saved as {icon_path.stem}_inv{icon_path.suffix}")