from PIL import Image

from src.pytrain.utils.path_utils import find_file


def convert_black_to_white(input_path: str, output_path: str = None):
    """
    Convert black background to white in an image.
    
    :param input_path: Path to the input image
    :param output_path: Path to save the output image (if None, overwrites input)
    """
    if output_path is None:
        output_path = input_path
    
    # Open the image
    img = Image.open(input_path)
    
    # Convert to RGBA if not already
    img = img.convert('RGBA')
    
    # Get pixel data
    pixels = img.load()
    width, height = img.size
    
    # Replace black (or near-black) pixels with white
    # Adjust the threshold (30) if needed - higher values will replace more dark colors
    threshold = 30
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # If pixel is black or very dark (and transparent)
            if r < threshold and g < threshold and b < threshold and a == 0:
                pixels[x, y] = (255, 255, 255, a)  # Make it white
    
    # Save the image
    img.save(output_path, 'PNG')
    print(f"Image saved to: {output_path}")

if __name__ == "__main__":
    # Find and convert the image
    input_file = find_file("gas-station-car.png")
    print(f"Converting: {input_file}")
    convert_black_to_white(input_file)
    print("Done! The black background has been converted to white.")
