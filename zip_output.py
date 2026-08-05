import zipfile
import os

def zip_output_folder():
    output_dir = 'output'
    zip_filename = 'output.zip'
    
    if not os.path.exists(output_dir):
        print(f"Error: {output_dir} does not exist. Please run main.py first.")
        return
        
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=output_dir)
                    zipf.write(file_path, arcname=os.path.join('output', arcname))
                    print(f"Added {file_path} to {zip_filename}")
                    
    print(f"Successfully created {zip_filename}. You can now submit this file.")

if __name__ == '__main__':
    zip_output_folder()
