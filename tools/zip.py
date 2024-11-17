import zipfile
import os


class ZipUtilities:
    def to_zip(self, objects, filename):
        zip_file = zipfile.ZipFile(filename, "w")

        for object in objects:
            if os.path.isfile(object):
                zip_file.write(object)
            else:
                self.add_folder_to_zip(zip_file, object)

        zip_file.close()

    def add_folder_to_zip(self, zip_file, folder):
        for file in os.listdir(folder):
            full_path = os.path.join(folder, file)
            if os.path.isfile(full_path):
                zip_file.write(full_path)
            elif os.path.isdir(full_path):
                self.add_folder_to_zip(zip_file, full_path)