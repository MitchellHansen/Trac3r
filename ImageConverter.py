import subprocess, os, time

class ImageConverter:

    class ConverterSettings:
        def __init__(self):
            # mkbitmap settings
            self.highpass_filter = 0
            self.blur = 0

    # This function takes a file and runs it through mogrify, mkbitmap, and finally potrace.
    # The flow of the intermediate files is
    # input_file.extension  : The input file
    # input_file.bmp        : The input file converted to bmp
    # input_file-n.bmp      : The bmp file after running through some filters
    # input_file.svg        : The output svg render
    def convert_image(self, file_name, settings):
        base_name = file_name.split(".")[0]

        print("Converting input file [{}]".format(file_name))

        print("Running mogrify...")
        start = time.time()
        subprocess.call(["mogrify", "-format", "bmp", "input-images/{}".format(file_name)])
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running mkbitmap...")
        start = time.time()
        mkbitmap_args = ["mkbitmap", "input-images/{}.bmp".format(base_name),
                         "-o", "input-images/{}-n.pbm".format(base_name)]
        if settings.highpass_filter > 0:
            mkbitmap_args.append(["-f", settings.highpass_filter])

        if settings.blur > 0:
            mkbitmap_args.append(["-b", settings.blur])

        subprocess.call(mkbitmap_args)
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running potrace...")
        start = time.time()
        subprocess.call(["potrace",
                         # "-t", "0.1",
                         "-z", "white",
                         "-b", "svg",
                         "input-images/{}-n.pbm".format(base_name),
                         "--rotate", "0",
                         "-o", "tmp/conversion-output.svg",
                         ])
        print("Run took [{:.2f}] seconds\n".format(time.time() - start))