# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from PIL import Image
from PIL import ImageChops
from google.cloud import storage
import numpy
import math
import random
from flask import escape

def GreenScreen(infile, inbg ,outfile='/tmp/output.png', keyColor=None, tolerance = None):
    
    #open files
    inDataFG = Image.open(infile).convert('YCbCr')
    BG = Image.open(inbg).convert('RGB')
    
    #make sure values are set
    if keyColor == None: keyColor = inDataFG.getpixel((1,1))
    if tolerance == None: tolerance = [50,130]
    [Y_key, Cb_key, Cr_key] = keyColor
    [tola, tolb]= tolerance
    
    (x,y) = inDataFG.size #get dimensions
    foreground = numpy.array(inDataFG.getdata()) #make array from image
    maskgen = numpy.vectorize(colorclose) #vectorize masking function

    
    alphaMask = maskgen(foreground[:,1],foreground[:,2] ,Cb_key, Cr_key, tola, tolb) #generate mask
    alphaMask.shape = (y,x) #make mask dimensions of original image
    imMask = Image.fromarray(numpy.uint8(alphaMask))#convert array to image
    invertMask = Image.fromarray(numpy.uint8(255-255*(alphaMask/255))) #create inverted mask with extremes
    
    #create images for color mask
    colorMask = Image.new('RGB',(x,y),tuple([0,0,0]))
    allgreen = Image.new('YCbCr',(x,y),tuple(keyColor))
    
    colorMask.paste(allgreen,invertMask) #make color mask green in green values on image
    inDataFG = inDataFG.convert('RGB') #convert input image to RGB for ease of working with
    cleaned = ImageChops.subtract(inDataFG,colorMask) #subtract greens from input
    BG.paste(cleaned,imMask)#paste masked foreground over background
    
    BG.show() #display cleaned image
    BG.save(outfile, "PNG") #save cleaned image

    
def colorclose(Cb_p,Cr_p, Cb_key, Cr_key, tola, tolb):
    temp = math.sqrt((Cb_key-Cb_p)**2+(Cr_key-Cr_p)**2)
    if temp < tola:
        z= 0.0
    elif temp < tolb:
        z= ((temp-tola)/(tolb-tola))
    else:
        z= 1.0
    return 255.0*z

def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    blob.download_to_filename(destination_file_name)

    print('Blob {} downloaded to {}.'.format(
        source_blob_name,
        destination_file_name))

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print('File {} uploaded to {}.'.format(
        source_file_name,
        destination_blob_name))

def choose_random_background(bucket_name):
    """Returns a random blob from bucket"""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blobs = bucket.list_blobs()
    blobList = []
    for blob in blobs:
        blobList.append(blob.name)
    
    return random.choice(blobList)


def photobooth_inputs(data, context):
    """Background Cloud Function to be triggered by Cloud Storage.
       This generic function logs relevant data when a file is changed.

    Args:
        data (dict): The Cloud Functions event payload.
        context (google.cloud.functions.Context): Metadata of triggering event.
    Returns:
        None; the output is written to Stackdriver Logging
    """

    print('Event ID: {}'.format(context.event_id))
    print('Event type: {}'.format(context.event_type))
    print('Bucket: {}'.format(data['bucket']))
    print('File: {}'.format(data['name']))
    print('Metageneration: {}'.format(data['metageneration']))
    print('Created: {}'.format(data['timeCreated']))
    print('Updated: {}'.format(data['updated']))

    download_blob(data['bucket'], data['name'], "/tmp/" + data['name'])

    background_blob = choose_random_background("photobooth-backgrounds")
    download_blob("photobooth-backgrounds", background_blob, "/tmp/bg.jpg")

    keyColor = [151, 44, 21] #Y,Cb, and Cr values of the greenscreen
    tolerance = [90, 130] #Allowed Distance from Values
    #GreenScreen('testimg.png','testbg.png','output.png', keyColor, tolerance)
    GreenScreen("/tmp/" + data['name'],'/tmp/bg.jpg', "/tmp/out_" + data['name'], keyColor, tolerance)

    upload_blob("photobooth-72a02.appspot.com", "/tmp/out_" + data['name'], data['name'])