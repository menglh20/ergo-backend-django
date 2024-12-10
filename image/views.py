import os
from django.conf import settings
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from PIL import Image, ImageOps
from django.http import FileResponse
import requests
import base64
from django.http import JsonResponse
from django.core.files.base import ContentFile
import base64
import openai
import shutil
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from io import BytesIO
import tempfile

openai.api_key = "sk-FnR6sw9wkaSRGPyMEgmrNl2m07hR9ZHT3hQ35NDMyij6lWni"
openai.api_base = "https://api.openai-proxy.org"

def download_image(url, folder_path):
    response = requests.get(url)
    file_path = os.path.join(folder_path, os.path.basename(url))
    with open(file_path, "wb") as file:
        file.write(response.content)
    return file_path

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def decode_image(data, filename):
    image_data = base64.b64decode(data.split(",")[1])
    temp_image_path = os.path.join(settings.MEDIA_ROOT, filename)
    with open(temp_image_path, "wb") as f:
        f.write(image_data)
    return temp_image_path

def generate_description(base64_image):
    model_name = "gpt-4"
    try:
        response = requests.post(
            "https://api.openai-proxy.org/v1/chat/completions",
            headers={"Authorization": "sk-FnR6sw9wkaSRGPyMEgmrNl2m07hR9ZHT3hQ35NDMyij6lWni"},
            json = {
                "model": "gpt-4o",
                "messages": [
                    {
                    "role": "user",
                    "content": [
                        {
                        "type": "text",
                        "text": "What's in this image?"
                        },
                        {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                        }
                    ],
                    }
                ],
                "max_tokens": 300,
            }
        )
        response.raise_for_status()
        result = response.json()
        print(response.json())
        description = result["choices"][0]['message']['content']
        print(description)
    except requests.exceptions.HTTPError as err:
        print("请求错误：", err.response.text)
    except Exception as e:
        print("发生错误：", str(e))
    return description
    
def generate_image(image_path, prompt, download_folder):
    model_name = "dall-e-3"
    image_size = "1024x1024"
    try:
        response = requests.post(
            "https://api.openai-proxy.org/v1/images/generations",
            headers={"Authorization": "sk-FnR6sw9wkaSRGPyMEgmrNl2m07hR9ZHT3hQ35NDMyij6lWni"},
            data={
                "model": model_name, 
                "size": image_size, 
                "prompt": prompt, 
                "n": 1
            }
        )
        response.raise_for_status()
        data = response.json()["data"]
        print(response.json())
        for i, image in enumerate(data):
            image_url = image["url"]
            file_name = "generated.png"
            file_path = download_image(image_url, download_folder)
            new_file_path = os.path.join(download_folder, file_name)
            os.rename(file_path, new_file_path)
            print("图片已下载至：", new_file_path)
    except requests.exceptions.HTTPError as err:
        print("请求错误：", err.response.text)
    except Exception as e:
        print("发生错误：", str(e))
    return new_file_path


# Create your views here.
def generate(request):
    if request.method == "POST":
        image_data = request.POST.get('image')
        if image_data:
            try:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]  # 提取文件扩展名（如 png）

                img_data = base64.b64decode(imgstr)

                save_folder = "media/"
                upload_file_path = save_folder + f"uploaded_image.{ext}"
                with open(upload_file_path, 'wb') as f:
                    f.write(img_data)
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)
        base64_image = encode_image(upload_file_path)
        download_folder = "media/"
        os.makedirs(download_folder, exist_ok=True)
        description = generate_description(base64_image)
        prompt = "Here is a description of a picture: " + description + ". Please generate a heartwarming image based on the description."
        ret_file_path = generate_image(upload_file_path, prompt, download_folder)
        ret_img = open(ret_file_path, 'rb')
        response = FileResponse(ret_img, as_attachment=True, filename='image.jpg')
        return response
    if request.method == "OPTIONS":
        response = HttpResponse("ok")
        return response
    return JsonResponse({'error': 'Method Error'}, status=400)

def openai_edit_image(png_path, mask_path, prompt):
    with open(png_path, 'rb') as png_file, open(mask_path, 'rb') as mask_file:
        response = openai.Image.edit(
            image=png_file,
            mask=mask_file,
            prompt=prompt,
            n=1,
            size="256x256"
        )
    return response

def edit(request):
    if request.method == "POST":
        data = request.POST
        image_data = data.get("image")
        prompt = data.get("prompt")
        png_data = data.get("png")

        try:
            # Handle path and OpenAI API
            png_path = decode_image(png_data, "temp_image.png")
            mask_path = decode_image(image_data, "temp_mask.png")

            # Assuming openai_edit_image is your existing function to call the OpenAI API
            response = openai_edit_image(png_path, mask_path, prompt)

            # Download the generated image
            image_url = response['data'][0]['url']
            image_response = requests.get(image_url)
            image = Image.open(BytesIO(image_response.content))

            # Save the downloaded image
            downloaded_image_path = os.path.join(settings.MEDIA_ROOT, 'downloaded_image.png')
            image.save(downloaded_image_path)

            # Clean up temporary files
            os.remove(mask_path)
            os.remove(png_path)

            with open(downloaded_image_path, "rb") as img_file:
                image_data = img_file.read()

            # Clean up the downloaded image
            os.remove(downloaded_image_path)

            response = HttpResponse(image_data, content_type="image/png")
            response['Content-Disposition'] = 'inline; filename=image.png'
            return response

        except Exception as e:
            print(f"Error generating image: {str(e)}")
            return JsonResponse({"error": "Error generating image"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)


def hello(request):
    if request.method == "GET":
        return HttpResponse("hello", status=200)
