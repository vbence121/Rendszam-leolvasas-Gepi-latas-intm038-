#from os import terminal_size
#from numpy.core.fromnumeric import size
from types import NoneType
import cv2 as cv
import imutils
import numpy as np
import pytesseract
import getopt
import sys
import os
from pathlib import Path
import re
from pytesseract.pytesseract import main

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\TIBDBQN\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
verbose = False     # if enabled images are displayed while detection is in progress. 
verboseF = False    # if enabled images are displayed while detection is in progress (they are all displayed at the same time). 
helpMSG = "detect.py -i <inputfile> [-v/-V] [-b] [-S]"
batchM = False      # enable batch mode
silentM = False     # enable silent mode
patternM = False    # enable pattern based otr 
recall = ""

inputfile = r"" # file to be read
Ffilter = "-" # filter used on result when comparing to expected output
Gsize = (600,400)

def patternSearch(inp:str)->str:
    if(inp == NoneType):
        return ""
    if re.search(r"[A-Z][A-Z][A-Z][0-9][0-9][0-9]", str.upper(inp)):
        matches = re.search(r"[A-Z][A-Z][A-Z][0-9][0-9][0-9]", str.upper(inp))
        return matches.group()

def ratioCheck(area, width, height):
    ratio = float(width) / float(height)
    if ratio < 1:
        ratio = 1 / ratio
    if (area < 1063.62 or area > 73862.5) or (ratio < 3 or ratio > 6):
        return False
    return True

def detect(file:str, eTresshold:bool=False, eBlur:bool=True, pBlur:bool=False, cMethod=cv.CHAIN_APPROX_SIMPLE, fSigma:int=15, ePattern:bool= False, aDetect:bool = False) -> bool:
    """
    Try to read image file and check result against expected license plate.
    """

    if(file == ""):
        print(helpMSG)
    if(not(Path(file).exists())):
        print("File at given path does not exist.")
        sys.exit(-1)

    img = cv.imread(file)
    img = cv.resize(img, (600,400))

    if(verbose or verboseF):
        cv.imshow("Color", img)
    if(not (verboseF)):
        if(cv.waitKey(0) == ord('a')):
            sys.exit(1)
        cv.destroyAllWindows()

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY) 
    gray = cv.bilateralFilter(gray, 13, fSigma, fSigma)

    if(verbose or verboseF):
        cv.imshow("Gray", gray)
    if(not (verboseF)):
        if(cv.waitKey(0) == ord('a')):
            sys.exit(1)
        cv.destroyAllWindows()

    if(pBlur):
        gray = cv.medianBlur(gray,3)

    edged = cv.Canny(gray, 75, 250) 
    contours = cv.findContours(edged.copy(), cv.RETR_TREE, cMethod)
    contours = imutils.grab_contours(contours)
    contours = sorted(contours, key = cv.contourArea, reverse = True)
    screenCnt = None

    if(verbose or verboseF):
        cv.imshow("Contour", edged)
    #if(not (verboseF)):
        if(cv.waitKey(0) == ord('a')):
            sys.exit(1)
        cv.destroyAllWindows()

    maxArea = -1
    absMaxArea = -1
    expct = Path(file).stem
    global recall
    #if(recall == ""):
        #recall = expct
    
    for c in contours:
        peri = cv.arcLength(c, True)
        approx = cv.approxPolyDP(c, 0.020 * peri, True)
        if len(approx) == 4:
            if(maxArea < cv.contourArea(c)):    # update max area
                maxArea = cv.contourArea(c)
                if(absMaxArea<maxArea):
                    absMaxArea = cv.contourArea(c)
            imgTmp = img.copy()                 # create copy to not impact original

            x,y,w,h = cv.boundingRect(c)
            cv.rectangle(imgTmp,(x,y),(x+w,y+h),(255,0,0),3)    #draws rectangle in blue (visual only)
            if(not ratioCheck(cv.contourArea(c),w,h) & (screenCnt is None)): # if there wasnt a valid possible match yet but the current one is then update the max area
                if(absMaxArea*0.8<cv.contourArea(c)):   # only change max area if the absMaxAerea*80% is smaller to avoid going over unnecesary contours
                    maxArea = cv.contourArea(c)
                    #continue

            if(maxArea*0.9 > cv.contourArea(c)):    # if the area is smaller then the x% of the max area then either try with diferent settings or return 
                if((recall != expct)):
                    print(" Recall activated")
                    recall = expct
                    return detect(file, eBlur=False, eTresshold=True, pBlur=True, cMethod=cv.CHAIN_APPROX_TC89_KCOS)
                else:
                    return False

            screenCnt = approx                  # copy approximate center
            cv.drawContours(imgTmp, [screenCnt], -1, (0, 0, 255), 3) # draw contour around detected licence plate (only visual)
    
            mask = np.zeros(gray.shape,np.uint8)
            mask = cv.drawContours(mask,[screenCnt],0,255,-1) # draw mask
            #mask = cv.rectangle(mask,(x,y),(x+w,y+h),(255,0,0),-1)

            (x, y) = np.where(mask == 255)
            (topx, topy) = (np.min(x), np.min(y))
            (bottomx, bottomy) = (np.max(x), np.max(y))
            x,y,w,h = cv.boundingRect(c)
            Cropped = gray[x:x+w+1, y:y+h+1]  # cropp out masked area
            Cropped = gray[topx:bottomx+1, topy:bottomy+1]  # cropp out masked area

            if(eBlur):
                Cropped = cv.medianBlur(Cropped,3)
            if(eTresshold):
                kernel = np.ones((3,3),np.uint8)
                Cropped = cv.morphologyEx(Cropped, cv.MORPH_OPEN, kernel)
                Cropped = cv.adaptiveThreshold(Cropped,255,cv.ADAPTIVE_THRESH_MEAN_C,cv.THRESH_BINARY,5,2)

            text = pytesseract.image_to_string(Cropped, config='--psm 11')
            text = re.sub(r"[^A-Z0-9]", "", text)

            if(text != ""):     # print out result
                print(" exp:"+str.upper(Path(file).stem).strip()+" result:"+str.upper(text).strip())
            else:
                print(" License plate number could not be detected!")

            if(not(silentM)):   # show result images
                imgTmp = cv.resize(imgTmp,(500,300))
                Cropped = cv.resize(Cropped,(400,200))
                cv.imshow('Original',imgTmp)
                cv.imshow('Cropped',Cropped)
                if(cv.waitKey(0) == 27):
                    sys.exit(1)
                cv.destroyAllWindows()
            for s in Ffilter:
                text = text.replace(s,"")
            if(text != "" and text != NoneType) and (str.upper(Path(file).stem).strip() == str.upper(text).strip()):
                return True
            if(patternM):
                if((len(text) > 6 ) and (str.upper(expct).strip() == patternSearch(text))):
                    print(" Pattern Based result:",patternSearch(text))
                    return True

    if screenCnt is None:
        print (" No contour detected")
        return False

    if(expct != expct):
        print(" Recall activated")
        recall = expct
        return detect(file, eBlur=False, eTresshold=True, pBlur=True, cMethod=cv.CHAIN_APPROX_TC89_KCOS)
    else:
        return True



def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:s:VvbBSMm")
    except:
        print(helpMSG)
        sys.exit(2)
    try:
        for opt, arg in opts:
            if opt == '-h':
                print(helpMSG)
                sys.exit()
            elif opt in ("-i"):
                global inputfile 
                inputfile = arg.strip()
                if(not(Path(arg).exists()) and not(Path(inputfile).is_dir())):
                    print("File at given path does not exist.")
                    sys.exit(-1)
            elif opt == "-v":
                global verbose 
                verbose = True
            elif opt == "-V":
                global verboseF 
                verboseF = True
            elif (opt == "-b" or opt == "-B"):
                global batchM 
                batchM = True
            elif (opt == "-s" or opt == "-S"):
                global silentM 
                silentM = True
            elif (opt == "-M" or opt == "-m"):
                global patternM
                patternM = True
    except:
        print("Input Parse Error")
        sys.exit(-1)        
    if(batchM and Path(inputfile).is_dir()):
        correct = 0
        all = len([name for name in os.listdir(inputfile) if os.path.isfile(inputfile+name)])
        for file in os.listdir(inputfile):
            if(not(Path(inputfile+file).is_file())):
                continue
            print( "\nWorking on:", file)
            if(detect(inputfile+file)):
                correct = correct+1
                print(" Matching!")
            else:
                print(" Result does not match or image detection failed.")
        print("\nMatch ratio: "+str(correct)+"\\"+str(all))
    else:
        if(detect(inputfile)):
            print("Matching!")
        else:
            print("Result does not match or image detection failed.")


if __name__ == "__main__":
   main()