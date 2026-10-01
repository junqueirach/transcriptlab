#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TranscriptLab - GUI
===================
Batch-transcribe video/audio with OpenAI Whisper (CLI) and turn the result
into clean, AI-ready Markdown via MarkItDown.

VERSIONING NOTE (read me):
    APP_VERSION below follows Semantic Versioning (MAJOR.MINOR.PATCH).
    ALWAYS bump it when the code changes:
      - PATCH: bug fixes / tiny tweaks (0.6.0 -> 0.6.1)
      - MINOR: new backward-compatible features (0.6.0 -> 0.7.0)
      - MAJOR: breaking changes (0.6.0 -> 1.0.0)
    The About dialog shows this value.

Requirements:
    - Python 3.9+ (Tkinter included by default on Windows)
    - Whisper (https://github.com/openai/whisper)
    - MarkItDown (https://github.com/microsoft/markitdown) for the MD features
    - ffmpeg recommended (Whisper needs it for most formats; also enables % bar)

Author: Luiz Junqueira & Claude AI
"""

APP_VERSION = "0.9.1"
APP_NAME = "TranscriptLab"
APP_AUTHOR = "Luiz Junqueira & Claude AI"
APP_CONTACT = "USEReira.ch@gmail.com"

import os
import re
import sys
import json
import time
import queue
import shutil
import zipfile
import tarfile
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter.font as tkfont

# ==========================================================================
# Paths / persistence
# ==========================================================================

CONFIG_DIR = Path.home() / ".whisper_transcriber"
CONFIG_FILE = CONFIG_DIR / "config.json"
DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"
FFMPEG_INSTALL_DIR = CONFIG_DIR / "ffmpeg"
ETA_HISTORY_FILE = CONFIG_DIR / "eta_history.json"

DEFAULT_WHISPER_PATHS = [
    r"C:\WhisperWorkspace\venv\Scripts\whisper.exe",
]

# Small app icon (32x32 PNG, base64). Used in header bar and taskbar.
APP_ICON_SMALL_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAADbElEQVR42u2VT4tcVRDFT9W970//75nOZGaShUIC"
    "0YgoDhhBwY2I38CN4DfyQ7j1E7hzmYUSRDFR1OjGMCaZ7p7uft3vvVt1XERBV/NG0FXO8sKtH6dOUSWJZEq78021"
    "PHd301A52yzUZD/F4EiphtCZNNPxaDjdGxd5oYCgkyQ1aT5fbOrK3Iw0wJ0iQoMmESjFSXM6AKr0y+Lw6GhQZN3q"
    "I9aLqqqqnXoT0cJyDYVraR7BRtVgIcSqakCEEJpkq/NKdZ4fz7IYOgEW65ULBApLRZ5Nh70hJE8pGlOMDUloU2+a"
    "1s0ACKFnZ8vZ3igb9kjIRZ2KW6WISrLSUFJGOcR3ddp6DJaEEoNmg0GRNVxXLV00ZGaJJACAF2YRd8ElsR8y26ZI"
    "eEib3ZKhbazONLiLUyd7B71eud48JkCn86/6XVpEOFXWtDjq1TEW497m96XSVIOKBBVH2FVrQwMhnBBzGKQrIfZ2"
    "1hTZWfAvf/7+/sMf77z6yps3b5TLZdxaDKAIiBgyhdKNEMAAA7oCNE+UGO/+9ODzB1+XN1749O4X3y2epCKXFjC0"
    "bWrqlu6iIAg44ISjs3Shuh71f92s83zw0dsfHE4OHpw+Oh8Wc2VldAktEIrCoC2sQWqREpJ1d1C0MnvcvHt8q+nH"
    "Dz/75JFW7924fbPS68PJeDIqe+VsNgtZNDoBgk53Et1DzmOo6ur63uTjk3d+WZzeeenWEanbejrIa6Q6Mcvjtm2F"
    "ru7KCFFx184tinXwVcaW9Yn13i9fxJmlo+zeD/effnvfSVe9enjtjZO36K1QhAQZHJdwgJT2kyRi6auqDFfyfn66"
    "Tg9/++are/l4MDs8MqqImhndFREidHYPORqQtYS452GZ2bSflfP65Zu3b7/+mqkuzzeT8dQgMRbGldNFAykinQHF"
    "dPJkswzGaQq9M0bbzcvQHl4pKNLaeH9kzuWqruvkjCFm7hgM+zHLAXThxGt7MzS22i13tEbhVb3bGIWeLBNJKZEI"
    "GpxACInepHR4fNwri44OhA3rbXq6mJ+u5jtPgKhRXCCSrCWpQd3NSBGUveLqwcH+/v4wateDQyMEZr5rm+QGQBx/"
    "TrpARPzZoyrJsih6Re6AdL9ol1iMz9TlCPxjTP/28eLxFpHLVP9XDi4pxX+s54DngOeA/wHwBxgmJBe3Khh1AAAA"
    "AElFTkSuQmCC"
)

# Large app icon (256x256 PNG, base64). Used in the About dialog.
APP_ICON_LARGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAIAAADTED8xAABbSElEQVR42u39abBl2XUeBn5rrX2GO70h55pQE4qY"
    "CgWgQAAEZIikxKZFi5LpCDkkuluyFQ6Hu0VFqLt/qMMOh/84oqPD/ccd7j+OkNlS+IesJi3JMmcaBE0SIKsAAlUF"
    "FAEUqlCouSqzMl++9+5wztl7r+Uf+9z77hsyK7PyvayXL89CxcHLe/c999xz1lp7jd8iM8ON00Fro0YiIiIAILK0"
    "yMgMi5OL0AEnM8SoPsYQLJqGEPycVJWZD76Em7rgW/v4LX7X0X3dbb4wIhIR51yWZXmeO+eYedQvHJNh/uSBqACw"
    "57m1bECBiAi8iw+MD2AwAgi3jejWBWD5chfvq4IIRHtuBADEGFU1zMlrjAEKA6CqZpYuSVU7ATg+ApD0ETO3fxOV"
    "0lKW5WWZ57kkUSBADaowg8iCB2J7pmMmAO7WxOeaorHgfgIMCEG99zGqmXrvQwhJDFTVa9RIRkl5cLrd6OiYUYwR"
    "QAghCY8BKAoCzIyIsiwryzLP87LM80wAYoYZiJLWMyJOPGIt41B7uJZWvTMEYIn7bed30ELSzRBVvQ91XfsQYggx"
    "Ru99umtEBCJmgrHRjlpKuv9aJlBHt5+Wd+P0XAzQGGEW1QBL5isz53lelmVRlL1elh6gKszMOba9OvO9teqxN4Fo"
    "h/sJMNDiR5qaRm28b+q68U0IMcYImKlFjTAwMzETEAkwMWp1ycIEOqLdvzOB3veF7dmZLcbkAbRWETMRmSqzFGXR"
    "K3u9fpnnzgkZEOeMvWzg0LWZ6k4QANr1gqX/DFGjmdVVE3xovA/ehxhMDQQmJqIYY9L9BKipGkC8rF32a51OAD7Y"
    "C1v+1OK5OBYmannALBm0yT2AGTP3er3hcDgc9lkkIgoRM9M+I3+vGNwBAnCg1wsY4H1o6saHZjZrQozJqU3GIC9p"
    "d2IW5sTlMUYWt3gkO2sWkaVOAI7lhZHZgn/MbOElp8eqqiKcZXme50VRrq6usMDNg4EMmLZ6744SgHk8B3N9D4B4"
    "zvrBV1VdN3XwXhUwssXPaVnZVC2FCoh2rP5k+RzWoz3+vH5HC+FCK6nO+YCI5gqrlYdllxAmzq2trmaZ6w96RSaL"
    "OCEvxUw1RsCSHXU7heD9CIBq+tXtZQbAh1BXVVXXTWhiiKog8AlQcp0AXJf4xj8uIkVRDIaDQa8si4wZBogtDGmz"
    "qMTEhNscB3U3fzeBeT4j2f2zae29r+q68Y3GqCkGpl3spKMdqZhVjRpi1Lqq+/3eaNjPHSml7E8kgOWDiX3fjAAk"
    "Y5539gEfNcQ4Ho9jjD6ENo1FZGaCLpbf0Y7ZxCJm8E1oal9VdQxhNByWpSxFPuy4C4DRLpd35kNdVXVdT6bTNoEl"
    "bK2FZEqAyYFCdNBW2u0Xdx7pQVaQXYOPmZlY1FRj0Dpubmvjm/W11aLIkt1jFg0QYjq2AtCaZwZVm/k4nU2r6cwH"
    "n+JiItL6R0SqSpCORU68Yr8pK2ge7xCYBq9TnTJhMOj1+31hwIxuewjo/fgAUTGb+clsWle1D97MRJyZeVPWpA+I"
    "WT7Y/HZHx84NAIWgRJYCRlE1xrjpN31Tq+poOMjFWRtLp9srAGYghfHu76UDfV8FqtpPptOqqVMRKGiu9w1mbQkD"
    "gfQaVh11knHCjCAwoCmyj13ZUVt6C0KmpvPgv5mpaTTDZFoZDKDBcJCJkKlC+WBDiPaI1KFIipunsHTfd+xKUChg"
    "itrH8XQ2a2YAsWMYoiraja0tbmqLn05ECPLWz2An9z6Q6ZxBFv/tl5CWtcxiy9QWW1FhJqKouj2ehmg+2spomGdM"
    "poaYxGZRbNf6oHsE4DBMJjf3WwxG2LHCyMzUsJyNrRu/PZ7WTa1qKWex5wI63X6XWjfXfPh2/QUxRHFCRE3jNzc2"
    "THV1daXMmGDJvki1M2ZkpgfHim55H3DXdG7MzFKtBzRa7f10Wk2mE1NT2+lW2RHQjjq6adFp2dl7X9e1ASwiq4Oc"
    "acHa80IBumU//FoCQLT/ZAaAWebbWOXD9nhc1Y2ZGSwV/6W6qE4AOnrfJCLLdV8xxu2tLWGMhj3HLWfaPK5y6Ky/"
    "2AEOblacF++g9mEynU6nsxhVsgw3VrTcUUfv7UUQJTWaWmoAzGYzZgjbcDjk1qXUI9WwbrdMLTaddh+ofJxMprPZ"
    "zMxYeKfVZe5FdW0rHR2OOWQWYzSz2azKnIgU/X6hgM1LD9qtgA7Z1+QD3ZbWRzHUdTObzbz3qftz0bN7/Yrljjq6"
    "EdJ5CBHzTnEismjTWT2dThuv80AQYjwqc8Ol5sSF5ZPUvwHRMJ1W0+mkbryqIbaO78LySZ+6WVuoi3iiK3RdMoEW"
    "f4jIXO1qrOoYr0a1U2vreU5GINkJyi/KsQ/U4De9Ayyr8EW8yoAY2zb2OSIAdUZ/R7eBmIXIea+z2WxWzY6a6dwe"
    "Aytxf4hWVXVVNz6EJADBiMyYOhno6Gh9ARCrIfownVTOTV2W9cuMCDp3Ug22Lyt2GD5Asn8SgzeNr6q68T7GaCAQ"
    "w8y6TFdHR78BWAqzOxeijbcnW1tj7/VAH/WQvm/R3EgwQA1N0KpuGu8tRgBqpCAihnU1/h3dBs84GijLCxJXN/V4"
    "ezyt6kX3pe021A9tB1g4Aqlnp66qGKOC29KlFqinM4A6ug1EsEWFATU+bG2Nx5MZ2R4P+3CY0e22v6BqTdOEEFSV"
    "WMzIVM1MRAgMix+0hdhaf7SDMsbLFSG2JKTzNnsCzSuddnCLMH/RrrPA9i/A/Nv2nAFmuO6CpZO36uy9vv3gBbsC"
    "4Yxr9hLZ0m0hu14dLu1cFun74deDK3IMu674BhcQEamZ995MybERTSbbTLo+7KktX/DhCUCC5hGGqTV11TRNG6A1"
    "FVjc6fafo3sedjjsBs+QSvBasAmCEBMRFGrBlIywQKIwMjIDEbWgQ7qTv9uJdhlakWZYNNsNcgSaL9D5cc65Oybj"
    "0nGPVmrPoEtnsMVbZtTWCV9jwfzIMDWjHRyO+ZlJCUYA73w1GQhEsFSqKMzMatEiDGwENgPUaPl3EhvD0kkYRoA3"
    "hBt+QCldyvNyemt/dcvPChNQnB95n4Sr6eKzOpdwshZHC8zEIIap2ngye3dja21thYGoSiBhiQrhwxCAReGDxpjU"
    "//KjoCXWoQ98b1RVYpgJSNNDNU41VEYtNrGRaeIOYwBkbKRk1N5hg8HIYMRkbETpaLpfsRGBbefYnkEXAoAFCzLI"
    "2p1gR3eTLZ8hLUALl2kgMt6/YGfHgqW35mp+V6U66YJxlxiaDGSKaFAzU7X2RxgAVoqwpBHsAEvYpJVYijeqXBfQ"
    "tukP260FUkPsriP2LbD5Z3mPTk/IaSn2kwDnxpPZcDh0GROYDq+txCVFKYyoNqvrpkktjsfS3U3KnaIQmyliTNUY"
    "BPPqE1CT8o4VpKnJTtlYaQ5S1ApA0jXprd0LFt+z89aBZ9izgGyfCXPwgvkZlIz3L9ixDK5xeenMAPGulmtF6sQT"
    "Ekmp02hqRETsdoWvaSn6sSv4mHSwHp+qdjMDzeHSAN/Uk/HUrQxEyAx6SG3kDkACaQkhNnXT4hYey5AnAQxOEItQ"
    "VYsWNWFSlhkrATDlhLRuAJExGyDAUoOyLVss6a12AR2gF2XpeIBttrzgGjGGgxfY/IS8Jxi9/wwJkHmX2qYEthx2"
    "f9BUvfcq4pL6VI0Akyoba4pl7/QcLswpXbJMjp3WW9xqJvI+bG1v9Xu5k9wSrtZhlKG5BYxzmkxhdlzVf/vojVTV"
    "IjRaCARoBIi9D/Pd2HRuTbPxfttt9w/c44fdJvfmpu5w1AMCD3O7lHdfGABjisRMYCaYaVQTzniv07j795IuIgY3"
    "dStuX2zUFBFVVdWVL8s8ge/TIbVEpuCrprQXgTTtPcfUBoJGjcET1LE4ARMhqvJcpzG01ZbMrZtGB7huewIg2AHo"
    "vQ0CcJMVhLwn2mJo+xHblltjpTYCpaoxxOCjExYmi8k2V1v4Kq29ZHvMp50d5jgVvOwUngEGiyFMppNevyxySSC8"
    "hyYA3semrk0VIFUlYhzLMk9mBiyaOqFBrxj0CgJUY5G7draApE09eYr7GKcNkhx8ZrtugG1xGjU9IIK3rDqv9dZ8"
    "wbXAb+hAJWwH7INKofW0LXn5yaq3etZsbW439QxR8iIHMzRFc3WPYjfa+1uVcKwSPWYpurzjO0e16XQ6mw2zrE+E"
    "GM3dMp6cS2i13jcENE0jeZ7QfukDQWl5jzuS+Npy56KGXpEVZU6IMSo0MiyFdxi7ZjGwQgk89/FsHsFZBi1QgJVs"
    "zgHpDyXw7mOKAqWQMFvSvjvH+XS09o8DF7T8rWQHnvygbyezvXJkUETjSMrzcBPISCQrMiFEIRNOkIORIWm7oLSv"
    "WxsKagO7OygOxz3Juaiankwmg0GeucOZ7eJUDdC6rlkkxOiIiEjV2BYzbQzLCZzbEvK/1i1QVVLNnKsmE2ME3whH"
    "C56I2xijLsVRFhGOBaK1zZ0923tcXrD41PJxJxZvB58BS21011owR8444Lj87bb01iL6s3weYSMYkxGBYUQgMJn6"
    "0MB8niFzLo3kIcmZIlLo0ObpnDnIWQv5QTsiQLhxSPqbCIzfVEG17eP7xUghAuq6quvgnJPDgBN1zByjzmYzZs6y"
    "TERCiMdXDxgZWA0EsTbDk9RyXIRWqA2up43AQKA92calf9LScc8COnABDv7soS14z8trQ7ApJx7ZQJYaNZRJmZRN"
    "TSPMM0UiJdIYZ0YZsRADxjBiMyXax8d2bOMfTKSqTBRCEOeaxpdl4Q5FAIiQYv+pH0dViZnVjuee2Eb2qY3kAzZP"
    "bSZ7P84zU4vKATsYm8Oue3x/b92uBbRjjM3tVANBCUpmBCMok4JSfjxGBZEROSJnBLVFZfG8/GGxZR7Xai+iFmgq"
    "hOBinM1m/X7PySFYQS51JZdlOZ1OAfM+sAjxMW1/IdA8oEFGpEQCv8QdtHe3OKFEyeox2QljUWQYIRIikzIiYGAF"
    "a8oQp+1QE8B3W8Ugc75XtKnxeJydATNNrcN1XTeNLwp361sAm1kIwTlnZkxt2uXYNvoaLIIU0Fb9QQEl3dsfYQeE"
    "yU8a7QPfnudMNcV4iJTIhExYmYw0mnrSaGq2mMvZ3iWX7pURH08raA7eBmKOMYYQmqY5FBXtzBIWBccYy7IIaqp6"
    "40Hx270BXJunbSmsl5DcTzT7E+1wcBvuJRiZkoHQusgp5OOEo2mMplEBMiZiseXKyrZk0I6t+jeDMMcYHLOB0mg5"
    "20HvuQUBCEEr3zBJNBNXQKLGSHIHtL6QLYo9eWnE+PIYwpNqAi3s/705hP1SApgwLFoknQd8iIgNZCQwp6nwaOES"
    "HFAtpwfVXd/ege6ptMVgzlmMaghBzRS3jMLvJlVdlINqNnNZPqkqYlY1LOG9LU+v+KDxBSzZrW2LvpkasQERcxDH"
    "tmE0BftTvOQE2j67arV0rg6UWcACJovJGeZ5LikySyasztQsah2tYckJmULNnJGYMZQS7MfuhttUwMoH8uQtxsQP"
    "Hj65S7B4JwJuZsQGIs6qpuFZNZiG1dGtqmpnKfC6gF889kpzwdaUAp1tBTJjJ/Hb3kNS4OT6wdr+wjbtN69wWuKf"
    "RbQ/Rc5svm2SwUiVU0NBGmWi7ZRz2ttuTgtb8gOuETJLMdz0c4XAh1IQ6lpbajdISwd3daJ2DDVIq8aNoEZCiBaQ"
    "hpeTGikRmRhiKqQ61lqjrXlR9d4DxaEJwM6uw9xBAJ0wjwHz3hiFCohI2mJpKCEqCGTadmbpsWX6lKdqN0DVpqnN"
    "hreoq11q/8XStOpO/Z/AgNHcaeDWf1YjilA2NQQ2mJGDqB3PTpAWgDBx5kIGmqaxW85euwT3mbT+sgB0m8DJEQAz"
    "MmuHMbZbgmYsbDDzqmqIDAciJujBEkDXjTbdJlpwaWr38f4wBmSkCoiFnHXq/8Rxf5sh49RGsGiJFONo0Uw1Qh0x"
    "RDiCY1sbeC0BwDHJlJlRjIcwVM8to9sutpg7Dr21o52xPpZmcmkM0UhZnILZoNBUYm8EA6nCSJldlmqrEGKMyk4k"
    "C9E0KjE7J7Bkduv+wP9tRg5eOAAJpFk1ajyEqk3Xcc5JifWAmZ1zIpL+YLCRZlkWDDBIsmwpRZFJNUWTlVPvpKVu"
    "0bYmkgSUrG2j42kXmNmhNK91AnCCREA1xuh9CDG02BXQWutFJjNVBxqZQU3nrXOWANHUjGI0JbA44TS7ZTGtcXfC"
    "1dJuEE/ATesE4AQZQczOOeecWmRiZoqGqHCczZG6NBU9EJSEAbKWs1nVGUiDznwDpkzyBD2SQAFPMCxyJwAnh2KM"
    "3vuEauODZ+KoQaP5Hf6NIG1LftoeKwczJTYjU1J2zBSiZ2EmAZRZRCQG7QSgo+Ot/okAZFk2GAzyImMQE6tFjcZU"
    "zAsZNAHLJCeSiNPoFQObmRpHctMmjmezGDy7dngKkZ7g+3anC4Ad9IfdJUO7d9esGYGcc6PRSDWSgiVVCFJUN+/2"
    "ShU/mlDziBjtgCwGoEYBzOOqqiuN0VxME+GYBScXGP+OE4AUtaUdRk91n3wQz/PJnOnRQkjQLnhDItGotW+YWyxR"
    "skDEAMfYLNUzp377tk1+UUZOBFVwXgiDVAkSPcOIWUKbKNK2vBpEJ8hwcHdWyL8tggaZqZkaAZY6hBf9rLxTDfo+"
    "8b7vDN0vtnsPMDh2kASpKXOIXQNIJMFGL5U00wF+LRMYqqHWqCCnSpBMJAsalCKgbZ1tC2p78MjSOy7/c0d3Tc1b"
    "xA82ge665JotIEV24GwWpdF2sOW479WdmuD2NdqNJHktE6wzgT5QOVjokl0NMQZ0c81uane9+351N+e9o7uaTog3"
    "0+0AhxReuOtuV7cDdHRX00kWgATv1Y4YmR9VT2xaZ1mFLxdOdnRoJpB9oEPyWrZebllO9b0HzTMwQESauur1eiIy"
    "m816vZ6ZNU3jnDuR3E9ECdcsyzIfQqoWVtUjEgMzu51TRQ44Q1cNej31D5pOpoNBn0U2rlzZ2NggorIsQwjtGKgT"
    "JwBJsKfT6dra2vnz55ummU6n/X7/BG96nQBcmyGALM+Z+dVXXvne9743nU4XzZ8nU+CJYox5nidN+cQTTzz00EP9"
    "fl9EOgG4GwUAsPTsNzY2Njc3e71eWZbJSj6RDEFEdV2XZcnMb7755rvvvvvQQw8R0WQyyfO8Y/S70QSqq6oospWV"
    "ldFoNJ1O67pWVRE5mb+XKMaYZHs0Gq2trXnv057QcfldugOwiHMuWQIXL15MExZAdCKtoOQEpznnp0+fvv/++xN0"
    "VL/fjzF2jH43+gBFlo3H416vd/78+ZWVlf5gYICv6xPsBqQdIMuyuq7NrCiKuq5PZNTraAXgNtf03ezX2fIzbw8H"
    "4HhojM65FPZh5qauUy7gBGvEFN1Kxh4zE9FhmHzz0WLLefZrwJHcZmbodoD32ASWlX2MMTU4neSfvBvhpgN6uqsF"
    "4EDt2FFHy9SlyjvqBKCjjjoB6Kijzgc4eYb/vHFyCQC4e+od7QjAsY14Xn+ltdQ2wi7gH5YbYog4BhUnKUOUxICZ"
    "77YJIC3cZwvyQ4sJK5iX1h6EjG9LN9muHfG028MM6KpBr3lXrl0ObUCIgZgSx4tIURTe+xDCXRURWvRCLLgfuwOm"
    "c9B9YDfSxIL/OxPojrR9YJZlGQDvfdKCVVXRCS2FuJ6fN58rkTKA6eenBFkauJt2RTU16N0WKj6ZApC289l01usV"
    "IiIiqRwgPey7LSGQSiRSGWzKDYtI0zSLjHhSChpU9a5zkE6mABBgBhbOs3x7vH3lyhVmDiEk7Ni7zQ9enn/FzFmW"
    "EdHa2lqv12PmNCXxLtQLJz4KZEVRiMilS5e+973vxRjTOMBUHtw+bDvBoJc7lPokkw+QBCDG+OlPfzrdn+QN37XB"
    "sTtSAG5IVxHNpjMnXFVV6gzMsizpuaZp7iptt6gGTTKQUNQnk4n3Ps/z5AakSBp1AnBYpEtz1qSFMGSyNOcd2D2F"
    "TVL7dju+Ko3xgcKMQESCNNtETc2YFKgsGEHBRmRGxm6BA0jGAHOaoE7IhEb9wcpwGFQnk2n0vleWcxhRU9npDWOT"
    "k/qMl82bRUtQenF59iiBdo9LxN2wMxxCOfQBHycoaRrHQ4AZs4JArLRAmrR2Yg8RLFcCYoSFNLhZYISoCjMWUUpz"
    "zs1IjdhcVk8nIk7VAFf5xjElnHsGyEiM2IgMeZZbXT1wz4XRcPD2xUtNHfv9ngOZb0CkHANrEIsUWcUlDPETagIt"
    "F4cWRZHn+dmzZ51zaTNsnQQYzFLU2Ad1GRmRqrKjeMPl0NdkiduIJ3IsdgCyhWbdecWIbEkAlJTAgM5EiUFgMyOA"
    "zRB0lBVqFoKPISpBWIo8DyFK3fTg2GgU2UVyLJq1ewIAZygCSySGghCF1Ky3Onxobc2Jc+KcgqKCYOQjW+QY2UjF"
    "RXeCHYKk7FMsSESyLEsoAV2FrDsi7mdrRYBa1k97ghm1rqcBRgpDpBihrf5WsMEpWImFMmLHrBLVoGa+tgxcgNE0"
    "CD5zTQ4NmUXmmYXGwWCqJEZiRGpBMIs+KsDMQl5NfUXRMiNqZ4ZGsCpgYDKhE7oDLKd7Fwngrk3saHcAmWdUWlOH"
    "EAmaEuw8dwBIYRCgz7lGDWaBtCabsYHdu/WUjTLOchIhYgUFbdhUzCOCtBAIwZogRusELxpYlSwyxgUMyF1Bmjuj"
    "djKuUTRiokAkkcSMwARNDoSmyaAndwdYFoPFvPVOAI7MBALRTlhBY5ucsoVz3E6zIKUIP54QOXUcHcecQyYNYXBu"
    "XY2aOtY+iI+inBF7iZQRQp5riKMVbz5uNcXU57nLg6pY5XSWWe1MGc20yVGSCIh8DCBmcQa2OaI6m4mJGAzwdGIt"
    "oAW7LxzfQ5mF3gnA9bgf7dCiXUMaAJ2bRq1okLEyrCwky8Q5IjaLdd14s++89sLGdHy1aTaqyTj4BmbONS7m/fze"
    "vPdgPniiOf/hweqZ1TN5ztOr7yLLPLNRzKLmUQlqXBo7IkkhjqhGMGMNBiWoITNQBBkMyTI4sep/wfHzMeud9X+k"
    "O0BbnCkGTaOpGNqWbZKyEbUjmhlAgFQZmVAI/ur29huXLr785htvXr18pa4nomMnY9GZcJ0hskysEcZZlZVx8yHK"
    "Hx2sPXbh/Ecf/tBjj9wffEXmCx/7IfZCZEPMpCIj9WzkHCs4goIhEimBAE2ORwQgRHpSBUBEktZf8P1y7efdLgBH"
    "UeE8j8m3HMUpJm9q0DzPVW02rYqi9EHrJgxOnZKi+O6PX3r2he+/dPGdd62eOGxn8P2sdi6Ii0RKZERstBJ7zqyW"
    "eHGUXUR8Vjf6b15efe27jzy7+gtPfv7J+x9wPmhQUwvVTLJCp9tlXrisF+oZ5VL5EBBdmUcgpRQiIEaAMR3gA58M"
    "OyEhRCyXAB4MFWFgZlNTVZFM1YzNOQkabrxv6uiq6++kcuhFMosMjPlwTkCYx1tjEbeyvn5lc1z2B6tr/W++/MM/"
    "efmFd6rxpe3NbTbfy6rSVYKZkGeOO9PdmI1KZVMEcT6nRtSgbP5dDe9Mx8/95r/5/IUP/c0nv/DZex5kr07KupmW"
    "xTAjqa+OEX2xXvazjLSuo5HAiJTAhEgg3JVZ0I6OMBPM80obazcBMrKIwWA0DeHtre3hmbMb09k3v/nUNy69/r+N"
    "35r1smwkWZYJiQI+aGbMLIERiGM6EgIjj8wRFFFGUdIgbix+PHRFmb995c3nvvLbv/CRJ37+Y59+eLCCmR9lsMa7"
    "opBshMZbNeOCmbEABlICiLs5Mp0AHMkmIAZq/zMGao1qTMNB48Pzl95+6vm/eO7FH14eiF44HXK2iEpVQyRjFmEi"
    "BacQPZSlPScpGTGJwpIvYXBc5v28Gm/lZ8+/M57906e/9s3XX/tbX/7pz99/jmKgxo+KrJfn/tK2skmZcfREpBQM"
    "MBOzCDvJInCDlsatd3h1ArD3lpKBYGwggzGMecs3Oui/qfW/+NofvnD50vCeC1dj4wORcWA0QBQyJnZCqhJJDE6p"
    "jBAFGwU27xSgwG1GzRnbTJutq708FyGfl3rvuWcy/9LXfvvvfebJn3/0w+dPrW5dHWMyEeeKMg+spEpGlCw0i2Rg"
    "k4i7ojK0o9snAJxmzJoxQAY1MuZiOPzuO2/8+p/+yY/qCT14z6sWp0GogTiwY4FEthBVg5IQz1VSShSbwSgSIkBs"
    "ks5tAAk7N2hMqxCccJ73Q/SbTfNrf/gVqqb/9ic/e2ZYVJNmJXPeV01VWyFtF7GCTLktcuEDA4h31Q5wF+YGjkgA"
    "jGAwUDRmMjViCTFomb948e3f/NOv/Wh81S6cv0ThosXRyqg/MWqCBlhGYlSANEREGFEkGMGLzbMHKghizKaAGCyQ"
    "BLYoHAmMLPpQz+rCsFKMps3s1//0j4zpb3z6CxyMJtOesENmGlnMzATELVRiJCIQ78kQnYzmyZQIS1mwRSnEe3yG"
    "7hZr6GhmhBFgwRH3CzeZTG2Q+6k/M1r/+ruv/fff+t9exczuORuMqmkoRqVFqqtmWJYzC1uoqZAi0npZhGllprOM"
    "PCBKBo6UihAZDAPBDFAmUFRtYn80DCE0vinzjF22MZ0UvaFy/588842trPxPPvElquJQI4foKAaJQYyNRV3DRCRQ"
    "iiHkeZ5lWYqaM/MJGKWRcsDOuel06r0vyxJL9aF7npqZtj0DQZ1rM2jEZLfsM9xd1aBkJgTSaMbKNCXjXvHOZPLU"
    "qy99x2/RuTMzj7LBKO8hQC30XE7EyvCF0xXxG2NcuXq6HHiLXoE8l4Z9VMvEUaY6L1dPLrBFYeqLxNmUwf0ii2aT"
    "UEuRw4NHvde3L/2r733no2v3/9Uz907feWfEzFAxJTIGKZkXZ0YZYTAYjMfjl1566fLlywBS59QJEIA8z++7774z"
    "Z85kWZba4lIe4IAEzu4hk7TUGNDtADdHObjR5kpoeqOhzeps1P9fv/P0d17/8WhtdcNHIwku1SZQ33iF88n2lDJf"
    "lNnMh0y172S6sVEOB/1BOa0qeO7nvVnjSbXIJCacj1RglxINBmYmANEcwEZmlmfl5tb49MqZSxcv/fM/+cpjP//v"
    "frIcGM+qOHVKZUBgVjAZWYBBiejixYsvvPBCCGEwGNR1fTKecVVVGxsbn/nMZ86dO9c0zfLc2I6OyMYljZFZaoZn"
    "6rvi1YsXv/7mS69PN51S4l/P8AIxcqq+qYm0l0nuI65cfXTtzN/+K3/tl7705fPs/JuX1l22mufTzcsZ00q/Rz46"
    "W+qqAVKeOI2FT9XUTpEZfNMUkheB8rL/wtXLv//dbzfDcpN05jIyKTxHIs9kIEec53kIoaoqVU1t47PZDEt1lHco"
    "MXO/32+apq7rNDcgzY3syoGOcAdgkPlY9Ao34O3QrEn/688/94OwradXKYCZAK4diWIQAWBSmoF7RTZAo5V+6Z5H"
    "/o/3f2Rw/0f+/PR9/+rZbzz39isRvLoyGOe2HaqcU3YBZBAgFVmzzT3vViSShLBAwtQPVlcrR7/z/ee++MijHz21"
    "WkwbMmNTM47MGZhMNcSi1zt//vzVq1cvXrw4nU5Ho9HJMIHM7L777rtw4YKZ1XU9GAwWYBCdABxhGDQaXFZuTSav"
    "bF769hsvXz0to/XV+sqELSdQimwyiJiqHL5p4DVnGwbcj+IeYAic/9BDD3/ooX/9zT9++gfPv1nPYlDj3Lm+attn"
    "Qwam9m/Ms2+RYACZlXlRT2YAKm+Vcz8OV//l9771K3/l587MMgWMAojYwAaCxBhms9nq6uqnPvWpyWQSY+z1et77"
    "O51LzCzEOBwMmHkymWRZ1g1OPXIBULOiKKZVQ4WTLP/6S9++yKEZrIxNHXGcY3eCwVAAFVQzNrLg61jNitpnEcNo"
    "jdEjBf7jn/zyZx/9iX/9tT/87vY7G4TagjhHQSmqI2YQ1JTVgMhQQiCLBAGL987lHjZpvDmJ6yt/fPWtn7148d8e"
    "nK39JjmCmRiZETE5zrxvzKwsyzRYzns/HA7vdDuBiPLhsN7eHo/HzFwUxWw2O8HTMo+FABhMmTw0C5g19bfeeXW6"
    "Pohw06Ypc6fEbMRthZyZUa7ksqwgjvA1miYHC2qPskAG5KZ/df38537xb//Pzz39b57/zo+Dn43HZVlmRV5VdaPR"
    "ORdhJhRhkcDOGSHUdVXp2nDNB2+ACoWy/6affOPll37uyfti48g8KZgFREHVV02vVyYjIfGHc857fwKe8WQyEZEU"
    "4V2Mjz8wyLvcO28GMyMmMz3BOfIjGZJnhO2myXq9kvIfvPjcjzGbjVZD7fO8VzsmIzZkCjJTg5itRI5N7aEyck0v"
    "ezdvNgAqoYAAZ4gLtUG0f/TE5//SRz/1q9966o+/8+zkyubgwjkUshVikyESjMl7r15zopwkGudFXtU1hMFcmzaw"
    "KsbvvfXWy+OtB8pSJ16AwrkYIzFzniV2Z+ZUQB9jPBluYhofn2SbiIbDYXKC9+uthQCwsJmpmSOKmhLuhz8k7ziU"
    "Qx9JFIgAE2KXTcaTNy5f3urLVTLHDuBArGA2ziNcRGSLbVEPQyiSBbbIiEBUAMiAEigC9Ru2cfwJKX7lp/7yf/nX"
    "f+mn7nvw8ss/CtPJaKVXs59KnKqnIu/3B9wE3Z4NLSMyCJyCDJGFjHtcvF1Nntu4OCU4yVLfJqtq8EntLfeLnBja"
    "MzmvcwCOXADMCAqXZe9Oxy++86bv5Z6JzalKYIAgEXlAZghslbPGUcMUGEoEmCgckBFytRzIFIgwg7AMo91bx798"
    "7wP/t7/2N/7Tv/7vjhhvvvwSRc9knFMMXptmJe+f6g115lU1komBlQBygYYxvzjefubyG1NGJgIzM4UZVLtKuM4H"
    "OEzHyymB5PV6/GY9KfPzFUiZA8DGrBAzMUSgcmgcmvQRo9IsDzZobAQMAzKFOSUCHJEjMDLQWpRx0A+V5d/+xGc/"
    "euHef/3Cn//hc8/EXkm9fjQOTZzatOcKNygbajR5BUAWkBkVkadqP55ubFOMzKaKENoGzS4k2AnAIXrBTk2jvlpt"
    "bhVUqsuhNZMZOROncGpsUUmVEQhMYIYoxKiIXETqA1kkqJIjkEKgBCWSCEdYYy5Ic9Uvnb7ngS/+O1+472P/y1N/"
    "9PLlS74oRmfPbVbVpatbXORSkpgFjmQyCHCRhIwzd2U2fTfWH+KibxDvLRNk3MXEOwE4vB3ALDfX+PhKtdkMs2LW"
    "5Fm2nREZZwGikAgGvFjKM5WBxVtmLI4MpIwaGGTGxkHMgAwGQgSMgyMQpOdjyc7DVpl/4kOPPrl25n/61p//0Qt/"
    "cfHi5XE/86cH2aCH6Tb5GEWKqCuVKFHIIS6bTWeXZuPNgayzK5pm6oJlznyCqeuo8wEORbDENTFcrqZ1L59UniKx"
    "kgBiSlBlTfAoDIghi5qpEszABo5gBSLPM2U7rjURicFMPYhIKW8wmNqqt08OVv/Rl3/mV37xlx4ejng2zRBm06sW"
    "gxJFARv6nrKIQBSdzOp6ezZVtcxlBAuM2DkAd+0OcBRxKwOCaCzyzck25cXYOSduMItFX2qrGoeImAUCyEWQmZH3"
    "okYwIU+ONCcgAs7ADZjIHBuQGxQMdkSK2gMB4kDESiNC6fj/cO/9D/6tv/N7Lz3763/w+35U1EU5SwgVymRE4AgO"
    "RXZle8s1dl4G1falTCIXve3ZtFAZ9vve+6Zp8jx3zs1mM+fcMY2E2l4cLzNzzoUQZrPZcDgEUNe1cy5VPdzYU7MY"
    "FQQi8iHkWYFUOO3QlUPf7NNRNQswANHQOCGiPEKCgVTZYMZkRCLGUGWOkUyJlciIIzGAtkdRU2uZRrAQYtUwjEtn"
    "ZQaYxcBmUCaVzNwK8Bjl9zz2+SLgX3ztKzWEirINXrctBIjCtWPyMfdKwsriLXLmcmvzACKyGKVxfBNhBwlAqvvv"
    "9/tmVlWVc26B/9xp+tvrA4C8aTBlkugrcRmITBDmGM5L3gIYLGrQCCIyTngqAQiAMkQUpAEIIAHl5BA1qk6ZIkiF"
    "BpJlYESLjZYZCdOVqt64eNlxLsSSGrxIPbnIagl9VxBCtKguc1Ej+ZgxheDJkHR/Xddm5rLs+A5J3CcARJRmQPV6"
    "vTTzIg0ESVMwOka/rQKgBEM01tI5nsUMTARj9hbBO8126f8kIelGViHAlBDFAhABDxOJBouAgRQiGUPYqGHAgwz5"
    "DKZeUfvesPQB3/jxq7/5/Wf/8MXvXCkJlLO1FXK1MyUjg8JcJixkUeHEIiMGIXHsWHg8Hl+8ePHq1atN04QQ0pDJ"
    "O2UHyPN8ZWVlbW3t9OnTvV7PzNJMtI7Lb/8OAA8loVFZuu0rqjCYOQo6by+aI6STgTXhEi62BIukEfCAIoAjoAYB"
    "oEDkyEwOmUttlyCFZkyuV155a+ur3/nuP3n6D15d49n5VTfsNdOK1JIM1E4NBjKLIc9k2C+g0ZOqI4qQYMFimbmN"
    "Kxsvvvhi0ppptvadIgCpffGNN9647777BoPBcDhMEwCOrwyfYAEwogDlTNZ6/Z4BwSoJJKIKXgzIoLacpE1CpRoE"
    "2jWp2WAwhZljNWgGRiQDIBRiFCUHLUTqaH/6F8//L19/6rkrb1xeLXFhfZObupnkxLkSA5FQszHMETT4wbA41RuR"
    "qUeQjMVDCBBOPl9d10n3i8jxVZ/7BICZq6pKlXyLOQDtAOCu9uH27wBGEMGAeBhJfaigmrnA5hiScHLBBszxOFOH"
    "++KhpmYBdWlojyEpMUpugQOARq0Pokx+9KN3fvNbT//eaz94yW/nD57z/fKq2IZFE+JIJRgKZQtsYurIKPhcZbXX"
    "4xnPNPZd7gCokYCZT585/cADD1y6dClNUrmDBICIyrI8derU/fff3+/367pOAyGrquoqn29aAG49Nlr7esj86PkL"
    "f/YX368LMGljRo7NdOEnUKvkEWDKFAmmEVA2MJATOxg8ACV2MIYRCDpVgw2GbjPYbz31Z//qz5/64WSjWR9NBmfe"
    "7eVXwyxGKqQs1fXMW2gkz1yWV8GDIjuicf3hhz80zIs4nnEmtQ8ZGEam2jTNYDD4yEc+8uCDDyYckeNbFXcNE0hE"
    "UhQovXJYBa1mH3w16B1lApnluQtVfd/K6dOunNS+X/amoULhEOezk0ARLexOBEVGuq+pWVGAuqmGWQLXEhiDONYR"
    "ZNITMH/7hVf/+VN/9IdvvnTpdGn33jMJoWKqKIQyF+XBjPpN4AwVIQJqSjBmMsQVch9eOVMq1BTCMTQENtiCXfI8"
    "L8syDZI4vrhAdvA8jxT/CSEs5gCcDGijOy0KpDYY9q+Ot9el/+FT519745XhmfW3w1jmHjAtN/ACSlC0PrEYnLID"
    "cmEmBgPgYFAm12MTenE8+Y1vPv273/n2y80Y956K/eyyb3zhoFIEWqlQRCNYcHAwkawijbHJTZhdVY8fHax8eHC6"
    "DDBSA4HZSNqsw7wWOk2WxnGui76GACx64TvO/iAFAADUJIRhIU986OE/e+UVXzdZKSGq7Di4u5+ctWUR804xFFKE"
    "ZibTGqOVSrgBvNCzr77xP/7JV7/++kv16UH/0YcuTSbTWVMMBxbUKfc9imhiVgsCG1RZMs+GYAVzsFA19YMXHvjE"
    "6EwZohEsiSIjBl2uClkw0B3kA3R0jARAiGbTySDPssZ/5Px9F0arl7fHvdHa1WZasEvMb/NhYbSDyhnFiBVsxsC4"
    "nq1kmVvJt802gHfGk99+6hu/8Z1vvj207MHzkejtre1AnOeDspZRQ04BQiNWCZSNYDFGyvNAxoxcEdRnmTx25sIj"
    "2YqrxzEFpNTArIROaXYCcJhhoNg0ZX+Vt+OZldVPPPjoD177Hu3W/DrHLxFjMk3WkRicQRQGOMkqsozc1Wr2W6+8"
    "9C9//6uXx9XWmcF4SA5sUy/sVgajpvazrUmZDxQaWBshz2BTme8kHlYSZ9EIes/99z52z/2notQ+xh7F1B4ldK2p"
    "z8fYljh4B+iQTo6HAJjlWU5RC+Km8Y//xEd+950fvzKZlINSfZMtek/JoJI2AVJYmqSkxpIxUJmyyiuX3/xnv/9b"
    "X337NTl3wffWt3Tqgwi5lXJF6ti8Pc4ly4drm/A+QyQ4QxaRGTmNRmIsQRuDcFBYePRDD3343P3FxbpuIg8cTBtV"
    "zcjSfKR9zHN8cYGM9lfyEnVjv45LFIjYZU3QHjltmntPrX78gXtffueH0yo45wKRqoE4hyvBwTTmeR1rNhaFZL13"
    "6vqHUevx5M9feP5rT33jHV/5tdMb0ah0RbYeYk2KsZ8VkaSXKVEV61iQEgBqYf8iIgkV5UwNkQ1RLTw8HHx5dPZ+"
    "MOKUWdUMiMysMHJ0YF3j8d4B7ICrvZXrnQcldrAhmFoEmxOMCnEkgVtCUDKiGhFAL8x+9pMf/3G8/O13Xs/W1qsQ"
    "cskdnHh1AVLkl9nqyMOiYEM5GP3xD78/dvzu22+9/sYbtRNbPaO9sgm+DpE0ZgkVN5MmS1MHAEDALraQ0WSkxBFk"
    "XGyMN4enh2661YTtv/mpn/z51VPlxtvmkDuu1IPIZZmP0bEQ9I4SgOtx8a1qr/k8bSICSK8Bi3JE5dA3cYbDMPiO"
    "akgeE4N5kiliHHg8YPLzpx/BLD433chWRtEEs6ghCpxT5okfivSNM6aJxR9Ptl//9teGw2Hdp6DsSg7kGwsuzzIQ"
    "hSbhOhs4VUsbKRk0YeWSKSGyKVFVj1dXV0r1rmo+9+BDn7nn/vUqsA8+Z49oBIDIzBmJ7TjlHXUm0GE4aAYQqgxk"
    "Ngj2IPUHpx69ujF59erG9hBbsc5Ag37hlepqdkZKVa3HkwlHzeH6g8j2bqxjbrnLLUNooqfIYCViMoKyGaf0lqqR"
    "KcXIMDZlxHaghgrJek+2Xn7tI2vrf+eLP30GZFXVG/anzRhsmmDcFS4SmQaG0V0tAtZCrnYCcDi3U9koA6upxjiQ"
    "7GzMfu6+j1Qx/JtXnm/We4PzZ7bG0zhrTo2G9fYsy3ImVvPmmHIJ2nDmGCAlipqpCeCiBYeQMZtmEU4tU4CiGLEp"
    "G9iMjbyA1CLQ6+UXf/SDnzxz4e987osPRD4L9J3UfgrXmrtOwQqJ3YzUbgc43B3AwApHyJgDaWNBtKHGHu2t/NJD"
    "n5pOZn9w9bV3+N240nNw49l2biRsLMRBfPCqwTTkZWmqsWmUOKPMSUaABzdsbMn6p1TlIDCyNOWLxIwiAiwj1Bff"
    "emDQ+/c+9/mffegxfv2NYZG53MbesyNSE4VTklSq3Xa+3O07AHDXbQFHBI8OiXCWhjDSLEcF7Znk4+ljef/vPfFv"
    "6bN/9BsXf+B7uRT55Ssb9w/OhiooojNzRs5RVq5UsxCiBbgo1GQMcUbwqqLtfEfPZqDARlCosSml8fRETiHa3NPv"
    "/Qf/1s88uX5BLl/+0Or6xrtvao8Go3JcTwvjIsApCAiUOng66naAw/OCk4niM4uCxhETZUy5J2qah0b9v/3EF/NX"
    "h7/7+l9cyuOZc6frqXqOGfFAckQNdeObWiAuL0ykhtVmQaFEWRRREEhJI6GRNOoRapopOxgrRIMjyRr993/+Z750"
    "70MrG9synqGvhWMvFrXJzIqAIoINkeAdlOA6CegE4LDiS2RwRKyoSRsCGUFDUG0GeVNHv3Hp0fX1v//xL97TH/7L"
    "15/9/sWLob/Cg7InRYzgCFDOXousMKMYDGYukAizUO6JvRpxcFJn2rB5R0EBjeXKgGs/fXejb3jiY5/48uOf+MJo"
    "uD6broH6ZdnEGRUE0diEzKhU5AEGRAfPAIE1Tdm4u8naOXlzkzDZhXZE5dBHFDA9BmFQQpi3fomB08BTxrY1ricD"
    "7lVXN0Zl8dcffXx0z9pvvfL95zY3x6pNM/XsHAvlHBnesSNGNFaWaKaqTWB2RZY3pJFjY6GJIRJEqBC3/cZbPa+P"
    "n7/vpz7ysccfeOSBfnluurVW+zIqk0aKymaAwDKFC/O2TIKyGiHTjv27HeCQKBImGQjIFAMPQGvGrJBpaByytdVV"
    "MfOzZrXRL6/df2aw/gdvvvzSxpUfv/PWRr0Vi4IGfR72NqYzi5qzFEQ52AXN2CptphRdLzNHYiRByftsFooQP7p+"
    "+onz93/23oc/un7mHA36W770sdDIUMACmZISTIx4MXOYTUFkOzNmOuoE4HB2gEZAhp5HFhEYDSNa7JcFB7ty9dJI"
    "em6l3NrekAl/dn390Uc/+/LmlRdHb37/8tsvb2+8sTm9dOVKbzS0TMyiAspsjoSJlIOG6JtmUsVQ90XWivzcYPjJ"
    "ex/4+JkLnzp3//3SG0ybfHurCJ6yYGSRTZNzDBIFmxmhzgxGKWuWRbvFGoKOOgHY7QOgLXdOhnUCJhHVXiTn9Wo1"
    "m/aoGAyZ8mKz6r290Se+UBSfOfvIG6fvfXFy9YfjK29o9cPL72z42TT6yjd1DIFQG3p51icnil6RnT299vC584+e"
    "u/DgytrDo9VB1aw2ftXXA28uKgheYzPvP0izwFjJCIGsysgICae6H8wMnmFd71QnAIcTBjUMG5ChzjAlKBkBa1Ga"
    "7XFUO3/6bIM4mY7FKF/pIWrTVCyRqTibce/U+iOnT1cZXxxvT3wzqWfTauZ9oxYpAYY6Xu31z64M711ZO9fvj0gK"
    "H3jj6krmClK1alMrES7yUiNFQmQCTAwukph5QS00zRAYebShR+FNgZhT6HpMOgE4LAHoeZDh8gAzB2foe+SNlpyF"
    "jJqqaqC5gYUnFM0F6Uvlq9BUIvnA5UNzzcQ/XKzBEfKog2gWU6NfU3AlqsH3iNaDG81iHjyFihBIazjSQkPJFevU"
    "qqLJRNNMYRMlZyaKwGxkXsizMQAPUhPCobTE7IRGyN47vWy0e5kZtUWedO2TH3mmKl0V7ezlu3/Yniu68wXgKOJW"
    "0VA5MMCWwu1kQMPGzimsCd6IRAQGVVUzjSBIDmZjDgYLhZnNxulpCBGQKhORGwkjNp4sZCPLKGf1WcYGjhY1KIEy"
    "ztlMTUmJYGRGgBJ5SmMkSRSDhgxgY1I0WTtc9Ya5nA5mBWpvRMLjBTh1OLQG4QEksAjIkgAokkQYlMC7j+n1dKQj"
    "4T9D6oyYe0QJXMKMQNLGQIG2l4mwAPi4UyKet9UJ9gIAopD5XfJCgJoZO0cJGcggIIGDgcgZE1osTuMdBMUUeZ7f"
    "/gAhdkYAORFiCxpBZhoSejoiI5IjNjiBYm7YK0Gl7aJySk531Nvs/UCn0d5HOb9CW3A7JdOPDlq/eH0PYk/qamjP"
    "oPuOtgMVf0Sss7/kmOcv0tIfcd+VdybQrQm+LboxDnoStJt1aOkzBzLXESuWa9XBcyv++1tISPdqiAMxHawryr7d"
    "1AU+jiIGxvN7e43bm3pAF4Kxc+y4/27YAe50BieLO5zK17Bt0lsKwOjatvKyAHQxqG4HuCNI30P/JzZmAr3H7d2j"
    "/rtcdLcDHFtajNFO/ksy1ZnIoiUERQKRERGrGhMTKKqKiNp89p6lGAuISOfhohQWSL2ZAF1TBMwW7cmp6d+42y26"
    "HQA7nSxHbPNQlmVpBAsAZiFmYReCOZeVvQRGS0QcQsjEMbNq7Je9EIJzeYIrYZexuKA2qxs1A5ERoqnLMs6cwYha"
    "57qttmzDXgQQiyPioBaipn8esbl0F+1F7mYZ7tBX3tQZ2mSQzZGlFwIwDyLtxCIP6RoSaC4zp8FhBiM4TyQgGNdN"
    "GGR5CJrnzknW1A3nbBqD9zHzGmJDIGEiigo1A0mvX3rfhBjzIq/rChpCCATrF0UTAkwMmgJZDAYBIB/V1IiYHROx"
    "AYaIw5b7ef1zuqNpW6K092gb5rV2O7KbFpIjQoW4dVHtfIDrqgfn0sy8ajaLMZZlSaCqDjHarKoHo5XpdLZ5dTPP"
    "CyFJY7lm1TSGUBbZlcuXV9fX6lmt0YKPVVVrhBlXVc0szK6pGxHnG69RCdT4EA1qMCI1sgRJQjSr6smsMlBelgBP"
    "q7ppmq6LufMBbgelSalFUYxWV6fjcVmWw9W1Jhi5YuPKFVW658J9Vzc3glevPnMiTI36sswAXV8beV+fO3fByHlf"
    "ZXnmnNve2gTlRDSZbIXYnDt3tqqqPM9EnG8iysw0wR4RETEzEa2fG1ST7el4MpnVGpXEFb0yBq+x6WDgOgE4Wur1"
    "ejFGEF29cuXXfu3Xvvv886PhyriORX/kve/3+v/wV/4vvaKAReYMGkWYQQy7unHlwn33/cZv/NZX//ipohwRwELj"
    "8VZZFr/8y7/8yKMPuzwvXX9aVf/0n/6z7/3FdwfDIcwBecqhEQjMAlLYsN//xCefeOLxT5w5d74/yi3aeDJ2HDKh"
    "Dgm0E4Ajd7JjjL08N9Vnn332d37nd+65577NSZByQCDv67/2137hM595YnvjclnkTKYas8yZRoJpaH7/937nN3/3"
    "T7K8LyK9fvnuu5fW1lZ/4Rf+HYBi1KJwqvTMt5/7oz/+6trqWggUooO19XFGYBCIsiz7n/7V/1zkxeOf/OQv/uIv"
    "fulLXzq1fqqZbmmcdUignQAcfZiMmZldngPIi7wo8tyzkhOWyXjy1FNP/9QXPj9hIWLv60jWKzLfVOcunH/5xZde"
    "eOGFc+cusBR1Xa2MRkyc5a5pmrLo1VU1Hk9XV0dlWa6srBZlqVN/+tTZuvEa41y1ExFCCIPRiqr+yde//idf//rP"
    "/szP/kd//z/85EcfbcuGOuqc4CPdAdLU9dlkoqqD/iDJAxHyzBVF8Wd/9mez6UycsBPnODmxs9mMB/2vP/3U22+9"
    "Hb3PxLG4rcl0e1ZFQ9EfRtXGeybKnQvehzqWxcC5Ynt7C2qOmVMRq0aLgVQvX7xoMT7y0ENro5WnnnrqP//P/vNn"
    "n/tOr7+iliaKtL08nUV0aDvAbR51dmyfXBIAETGzLMvqpg4hZrlAI3FgsZdf/uG3n/3mF7/w+cuX3y0zl2XZeDIZ"
    "rIxi1fzZ00/nRZELQjMry3xzWhXDFRNXNY0BToTNN7Nx4TIGB69mIsT/9//rP/rMp55499I7/X6vmk62t7ee+fYz"
    "z//F88889913Zttr62cyHzauXPmv/p//7//6v/5/PfbIo3U9I0TTIJAYfJaxmi0VizIAws3WLbdluaYKIzW98dLP"
    "O44Zuh3gpvgidRbQhz/8GGAiNJlsP/Ptbxe9wjQakQKSOSN68+233n77HTCZ6cMPf0jEMXEToydll4GMESmVf7Yl"
    "sCzMo5WV+++99ycee/QTH//I4x//2GeffPKn//Jf/sf/5X/x//1v/9u///f+7pn1tXcvvQOzXlm+9KMf/dN/9j+8"
    "u3GVnGN2TYwg7g/6qrrsFyihM5Q6AThcl0Cm0+mjjz66urqaZRlATz399GwyJWJTNYVjl2f5d577zhtvvMnEqvqJ"
    "TzzOzCISY7RozAeoUyZqmubqxkbjm6BxNqs2tzY3N6+Ox+N3X3/TzP7Tf/Arv/IP/2Fe5GWZ50UuIk899dSLP/xh"
    "ssiEpa6r4zvOoxOAE+MSiPD25ubp06cf+/BjdV33+/3XXnvt+9///mi0kvjPiEWyp59+elrN1FCW5Yc//OEYIosQ"
    "kcFU4/5d3sxYuOyVLks+BjMTANVIZJPJRAk/91d/7ud+7udeffWValbde8+9W1tbX/3DP2yaJsSY5zmzNE3DRJ0j"
    "0AnAUVpBxCH4Iss//elPz6ZTZprNZt/4xjdGo4GqGsiYr2xsPP+d54u8iFEfeOCBCxcu1HUtSVenqWQHiBaBYFDf"
    "eF/XIMvzvOyVRZE7J71+eenN11fX1/7OL/9yv9/3oQnBxxi/9ed/HmMMPkSLZVm2I4E7m6cTgCPdBJxzMTRPPP74"
    "qbX16IPF+M1vfnPj6maWFzGak+zbzzz7xtsXXVaGqE9+9rMrKyvT2TQVjTKzqhLxviIWS9lfM0SNqjHGGHzTliF5"
    "v7q2trV11Uw/9tGPivCsqgaDwfb29nQyyfOsqWozZeoqqjsBOHoSosl4/MB99z304INOJHj/wx/+8LXXXu0PBj6G"
    "Mi++892/mFWVgZsmfOQjPzEYDKqq8jEAIGZViPDenk8iM4sxiKMiz1I9qc6pKEvvAzM//OCDZ8+f3drcLIocwHQ2"
    "e/nll4uiFJEYAoi6nrKbFgA7iK4fFrzBxbd4Brs2LUqGl+aiH86DTwy3uKTlNgBVM1NmVmA2nZ45e+4TH/t48H7Q"
    "H7z91jvf/tZzIfgsL66Ox88886y4bFrVDz78yE/91F8ab497vR6BVDWGkGWiqrY01Z0ofRGYKTUMMLNz7JxzGXtf"
    "m4Us46qqy345HA1EWESccxrjeDIpioKIfIhEt9xR3NaD6k4e7tqD0m4nMxzK13U7wA1odxERaY3pg1wAMyvEOXFC"
    "9MQTT6T1qvb888/HGAf93os//OGPX3mF2TVN8/jjj6+urvrgJXnA88lzB1d6G2BqpmqqGlQtoca4zNV145wTRoyx"
    "qT2xeO8XOYrGN0Qk0j3KTgBuwbKPMSbdb2ZpHzg4qmhg4UzI17MvfO6z58+f994P+v1nn3nm3UsbRdn/+p89/e6V"
    "qyQZifvcF764s5MkO+eGdHBKOCQNp0TGzN57ItIYZ7OJqg/BmxkxD4fDpm5AJOJUtRt43wnA+4vttLXHi401vXLQ"
    "0gTmpbNZdeG++5588snJZFKWvddff/27zz8foj7zzDMuy2LU8+cvfPpTnwLQGhREAJjarnnaz/jQOaTLvO8ErQSW"
    "ZVbXM3Hu4qWL2+PtLMvSllLk+alTp1hYY4co0QnArQmAc27B8USUjOxrOArmSMxUvf/yl/4SGYKPgLz04o/eeuOt"
    "H7/yaq83GE+mn3j8iXvuvX9Hom5g6vDC+F54IcnIqetaVUenLrzyyo9//PKPB4OBc246nZ45c2Z9fd2JqKkZmAhd"
    "FqATgPdnAvklapqmrmvv/XW2C+fcZDL52Mc+9sgjj0yn036v9+orr3zt61/f3NzWqFmWfe7zX8iKPISQzJq5t07v"
    "fSlQIsXOqGqr68o5N51c+da3vvXO22/nea6qPoRPf/rTvV6vrhtOotXZPzdPx7kcmnYDwh4hLGxS04PBsCiKpLND"
    "8JPJdCnCRHM9DjP13jNxsLC2tvbkk5998Ucvg+z7P/jB9mQKI1U7c/bcpz716eC9xGgEIt6Bg2vZep/NYmZqMRlY"
    "qT9XEdTPprPRykrZG/zWb//WV77yB/3BwHvv8p4wffnLXx4NBlcuX+qVOZt67/cHWDu6UwSAdjjcFnayzuGlFseF"
    "bCyHxm6V+8EM0IsvvTydzQaDQV3XMcZHH37EFFE1z52qd5JBmcDBtFHfhMYIzPSZn/zMr/3L/z8JXbl8ZXu8Nejl"
    "k8nkYx957NzptWo6LZxECyHWPSqdejERi76piRwAI5cm1CQPJHeuLHsimZoohF1WFo7Z9VZO/+kffeW/+yf/vzde"
    "f/PsubMAv3Px7S996S995jOPN9UEFlnQ1J7atvblhuFOGN6XANzmolbT+UQx2/PgeI40OD+mWt+EpfN+USGWbXEz"
    "CyGU/VHtw3/3T/77r33962fPnt3c3Dx39uz/57/5by6cPz+bTMXlQMPkYtC6jllRrqytwLHGwMwf+ehPnDl7Zjar"
    "wFrNJr1eX9V/4fOfHQ16UTXLs6JXMEVoTWHGnLEFBkmWBe99hI/W+BBC0zR1v9/3japSng+cy8eTSR3s7bdf++pX"
    "f/W3f+u333zrrcFgpZ6F2Wx2en3t//Qf/K0zp0ZvvfVGWfZC8CGGXln64GkZYSuhGNkNP7I9UfblWXm3CxXiJAzJ"
    "e1/WznVep+uuOQQP2ExDDFVTb29vl2UxnozzPJ9Opxpj4xtXV0WRq8a8LFbXVl5/642Nq1dTxEiEL1w4/+lPf+r3"
    "fu/3zp07B/S2trZOnVr7+Ec/CrIQmnHTmMYsE9WQZQyLs9lUCFcnY1UVJ2AqiqwoiqJuLl689Ku/+qu//uu/Ph6P"
    "B4PBeDyOUV9//bXXXnttZWXl3nvvHY/HdV0T8z/4B//nT33qidlsUpYlM7z3LNxOO+4cgZPiA9w+8YsxhMb3ylKE"
    "nXNrq6uj4bDX67ksc5kDE4lUdeV9U9eVc9zvl0VRTKaTyWR87vy5L37xi7/7u787mUxEZGtr68knn/zwYx8GwQe/"
    "MhzFOaWs2crKKO+P7PLlXq+XZZmpeu+ratbr9QbDlRdeeGE8Hs9ms9Fo1DTeORkORw899PD29tbVq1en01mv1/vH"
    "//j/8Uv/3i/U1WQyTwOnBIbG2HUJdwLwPqw1zfM8knv30iVVHY1Gr7zyymwyTRaXsDBz8E2q6QegatPJzNQKl9fT"
    "igyf/MTj9164Z2Njg0H9svdTX/hCmRdVVcUm5FmeuDbJQFVVW1tbTTUNIRRFkaDmYoxmVtd1VW2JyOrKaH1tJc/z"
    "yWRKhO2tjeCrGGMEfuanv/x3/+7f/cQnPl7NZtvbW+l6vPcpgBtCuHYOu6NOAK5tAsE0+GZtfX19fV1V+/3+vRfu"
    "qesqlXA2Tb1x+crKysqpU6cAnDt3Lndue2ur1+sNBgOL9sADD3zuJz/3lT/4ymg0unD+/CMPP7K1teWc6/V6RJS0"
    "+/b2toicOXOm3++bxizLAFy9enU0Gp09ezbVX5w6dco3HkR1VXnviyIfDAYPPvhgURQf+9hHf/qnf+bjH/94Wfbq"
    "elbXszzPi6KIMdZ13ev1UsNN9zRv+ul/9wcvHQMnWG78tMSE2BDC+mq/zElDnTnA4twJZqRBPyC5xgyfPU6wqpII"
    "Z/nm5tZkMmZmMyvyfH19PdQNM5dlycSbV6++e+nd4cpITfOyOHfhwtbm5nQ6zfN8NFq5dOmi9z7p4Pvvvz+10qtq"
    "URTBhysbV4qiMMNsOj13/pyITKfTtbU1VX3nnXe893leNHUTgjrnsjyPc12ebuODjz7WTMdmluf5q6+91u+VZa9g"
    "AROlHFmCLr2WAMgNO8Ekblw1F9+9WtWcSZ+ynikrqXEARUrzZo3J6IbPepROsMWffPJxd2tFUN0OACJS1Xo6HQz6"
    "p0+fIiIfghBVVZXK96fTqaqePn261+8zUVGWk2o63t4WkfW1telstrV59dSpUzEEFsnzfHNz0zlnZnmWJ3f2zJkz"
    "IQTn3Jkzp2ezacrvXr16NYRw6tSpXq9X17VvfK83DCEkaz7L8xShEuZLb72R57kIb21trQyHRVk0vjKDVzWzsixV"
    "dWEIdXRzApAi0KkULGUr0x9HpewPYW9J2LGpHJrn1crv/xqIiIEsy81sOp2lgXzekLJgyc4Wcdvb20SkQDPeXuTH"
    "vI8ZC7ELdQMgRp3WTS6uHZQXQlGUydBPN3k6nabLZWZmyfM8hLC1tUVEBJpNxjQvFGpm01TfHyL1iszMLMZenhkQ"
    "vWfi+eRMShnrw+H+1JVDTEs36uie7/tghnTrWuenibee6HAisuD4uxtYRufW0WIo5fLd2Hll11tEe0CK939wn/Vl"
    "exhg/mIaKNnOlQEZIIACYhbbJPJOdPiuNvdTkYgI33rQ12VZ1jSNLfLzN1CzdVLv6i4e268LyA7i6QPm/b3Ht7zH"
    "i3H33zY/3u053bRzzpuTVETyorh1VuU8z5Ole1gmSkeHKZMHyczd3Pi4sNKZuSiKw9kBljvfUhd2ioR0DHgNO/km"
    "+PdGJsa/jzPf1GlPjNmzsFOSvi7z8tZ3gFYAllv1umzi4UqL3YS83Ng6AtmBA+tPsuJfmP6qlnqq8yK7dV5lSRAd"
    "Sd+rtaW4h6wu9xxpaZwovY9dbF70QgstaLQzn90oTfgxAxLyoJEBCYVw54+lt5J9v+e/OUfOFxhsDmW467N7vmJ5"
    "AVLkfGnk/cFfMT8uX+c1jzCCKe0/wzVPbte4vP3HXVtM+op2fOX8/s6BHI9W2dO1XCVNI5bNAgtEDkEFuH7P9Xq5"
    "htwH7yQLGoQQlyKhuvNrjexGYVatvV8M0vmRsKiDTwD46a2biZEpSIgTECcAtXQKU7P5uQnzi4xQLH03dtdb2+6L"
    "S6D87WMmMyOQxd3dCPPnsnz17dF2lu1aMFfXS8cdHb7ruEAJXWwHy4XgdOCuctB5diyk+TG2V37A5e25frIkJTAL"
    "QCAOZkwwAwPSPqxW2ZDdTCTqJhJhgNLiWnf4jWFEShZjDGWZj7c3+w/ff+sS4JgoY6b04zTI/FEfghRjLgM7xz3e"
    "Hb+PDUWJrB3GS4Du1U1zSW2njqYp1XMtt3RtO2/p0it7Fuw5mu36guufwa59nut9xZJO16WjXStAdWMnt2tc3vL1"
    "GyDthpy2rwiKMAXx/N4feaJtofsXgrx47kTQqEpgsjx3RMjcIVyPSzNA23RYCMSsqsxyPF1ggrHp0qB2ag2TebW6"
    "ERk43Ti2LjN6syGno+28u5UHnzA1Us5KRHq9/qHk/hwBeZ6nUiqvyiyA4di3VzOUTBlku8HvyeYGTFrV0U1JgDFu"
    "fBbA7b02gwmnvn/z3q+urh6OAADIsizVk9QJmuxYs74SwKYLN4kInKwC2u+4djJwKM7nTlC39bDppqJWhxMDVYtO"
    "XJoZ5b0vivLQBECEUj2WE0kYrcc0CUDzrrz2MSgZk+1xEdG6ky3rR0CAeNC2bvO3DlzAS2/tWbCIXy0v2J+s3XMG"
    "ve63yz5fV697ebdy/ddaMPdxwfP/rhOovd0cMu/EtARg0++XKSJ2i+aaM4CJ8jxLzkATIjPFqHR8SwsNpEuBKdCS"
    "F9yOOG+HBBlIYTaPhyxHQebitHPcs0APXrCsCnctwN6m/r1n2B+FsgMW3Ojl3cz1t8JJeyNqeyKnO2GE5X/S7tAU"
    "FhHm2+kqMDPMfNMANhqNyrJ0jnwI4uQWIzZO1YRJhLMsT0VBAFKR5f5iQLq1CNetxshsp5iMic3UTIhFbccrNkpR"
    "IQGMWGF6cF8xXfd4/beYll5cMrmWa9Xe38mZdi8wLEKBu89gN/UVBzPrXsgZRWTkKeRPIGaBUQsWuYjewtqQ6S2H"
    "O69zhj1N/fPgmAFwzsUY+/2eExfjIUBBurbsUKQsy6qaIQSbn3WODcCLLfODDw8Q1KAGJ2RKIGLJoVUkItvZwa1N"
    "3gB8HUyh9wQdOngB0cELDkS8vamT736ay6fdewbb0cF7A/xLjL94a38uAftRZwxEDGFJ0HhIAHW7jAzdwYYAQHzb"
    "6jESYis7ybKMCHMHgA8jD8BIqHr9flnXvappopqBbCklPEc1sw/aPyZN8MkgMygoJqOHMmFtbWJlY4IydgnCHka0"
    "a6Bu3ciCBZ/ue2snVk/vcYZrfS8dtMD2C5IRuI3Q7zrOdVf6Y/4Ws7shATABscKYRC2EGABmzowo7mDNLDsAt9UK"
    "cs6ZqWo8dersYNhPAng4TrCqEVOWuX6vtz2eqIWEMrDM/YeAPX9IkboIglFQrZtgxsKREalNF0UQGdggRgb2KRt7"
    "Q+x3gwtwQO6V5v6ZXWfBNRO175EmhtoBC9L/LNre454zRCMwmVH7vzZIcOD/NJqhrlTVYGRKJAduXNqmkm/vc6c2"
    "/MSrq6N+5mZeM0eHYgKlGBMJIS/yvCi8KjQc00xNigSrBdVp1dR1hAVohEaQ0XxwtIGNDIhKygYlLI4pkrrnxRtf"
    "cB0BoNSrhnbl/mWLM1xrQfJX28qEGxCAG7x+WjrD9cWPyZFxVCXi1G2HVHpJB0Xkbm8cVA3M3OuVeZYDUI12GA29"
    "DvNuOgOcc8PhsG6aEGLKOOx2a45FBS6JmFnUGDU2WpMpmabRKgvTOOX+zVjBB9q/uG6xDQ6CZaTdBvj+BXvswz0L"
    "7Lrffp0FZHaL1w9VO8CZOgh30oIQieTM7cyy9ufOvcJ2R93ladymPJiq9cpyZWXVOaeAiKPDuIAkAFC1EC0THg76"
    "2+NJXfu2kGdJBo6DDWQgUwYzkcALcSZkgkjMqTrUwEacMpoxDVG6oVK0G14wD1McvgnUlvti+eRMgBofcHm2WLA4"
    "7rl+XjrDDe0AgEYvsCzLLIQYlc04xQPn9/6D68YhMy2KYm1tlYWjIXOHMxHQ7QTNDACc8KBXzqazaEogBbGqLrbW"
    "D3QLSJuSmbaN2y4nOCE4thA8wEYEY9C8VZSYWnMBiyOw65/7j++xYLET7ntrp0eF3usM13zL9n+7ke2/vHacEnac"
    "5J3jvhex+++DP2UwgJlEABYiKDyUmDAvDliUp9HCDjuKVCfPMxSL7ZaImJSI+/1er8yiGlId/2E44Y4QE6vME8t2"
    "5tRq9GFjcwxm81GVCK1BaHarffi3hA+TIrKttmQCA1DTJgCWLWWYqK33vZmHdOsB7AObM47otEQHWyC3/HWZV4Ua"
    "kXO5g5EqCES7ix9ae0Bx+MxgYMeAprrMNLoqd8TEg37/9Ol1oXbDSoHbQxCAPa520i794SAEbE2mauokY2YfYzTj"
    "D9oJWGpbX1yKLOu+Pdquo/d1j+kaN3CPFXwkt9hgaqpmbCbCTFCNLuPRymgeJsAh8qHbK0REAAb90iJmdT3HtGGi"
    "CLUOebijo5a+NvtKRMxkaqYi0uv11tbXxUmqgWlz8YeVB9hPTCjLfDAcRNWmCRqitQPeOr3a0RHHOdSIKBMCWri7"
    "Qb9/+tSpQa9ow3tGRuBDCkIdLERqEMfD4XAw6IsghAAoSycAHd2OiCcAYU4jO53I6upo/dQqEYjAtr9m5HB2ANod"
    "6QYTej0Jod80VQhKvIwM1VFHR2YEEcFiCEqEsiyGg+FwOCqctFE2As8bmA/l6/ZO3dpjCBVFXhRFnjOgGrV7PB0d"
    "9QbAZGbqfWNmZVEMh4M8zw2IahpTIXBqgD0cdewOtIJ43sJeFHz69CmXuytXrtR1kzon29DsHL/71sN/txNe9zhc"
    "2G1Gn//A7/m1zhBCSIMR0pQqa6cFKovAVJjW1tbuvXCWiIKPWSaYhwGpLV2wW+/4e+9qCpdRWeb9fl/VwhJu/UIM"
    "Ogy5jt4n87l5KZq2fQdQCJlZFJH19fXU+EsAuaVO5UMtQ3pvASKgKLKVteFg2Etw4cxdNLSjw2A+ZgCJ+9M/iZCg"
    "2fr9/rlz51YHpUYLUZnm6Qk75CI89x4eOQiAE+n3e6bwTWyaxvuAOXB+p/47uhW7KPFPMoRAUI0w9Hr9c2fPDge9"
    "5OvSogDjCEpQrw3MBjMoEBMSoYD6/XJ1ddU5l6BJF5M1ugfZ0fujZUYySy1YVpT5+TOnz6yvMRCjMZMw6TKbmcEU"
    "pociDO5a3D+3thYN5+ZYhqNBjBGwtAl01NGtKmBiUJqTiTzL8iI7vbZyav2UODYDTAmCA8aOLPEpHYEALDANU2GZ"
    "tpislDteXV1h4s2tzdlshrZRbQenjXbJT0cn3Ya5sZbnJXZdVOcmTa4gAlHUyERlrzh9+tSptSE7DtGckHPStqUz"
    "78OVwXKB7qEJwDIswaJnYl5wpjAtMnarQ+dwdROzaR1jJOa2oRocNQIQyVo45YPMvmvI2w2tvFkT8ygWH4cA4rG4"
    "DwQlsEIZrK2+bDHK9rVYACrOEZOqxhjJwGKSUHgNmaOyV6yvr5w5tZI7Uj0QCYCW1KzugM8emRNMCxdh7iiwkhJU"
    "HI1GA8AY29NpZUQaTImE2dRiNDCD4oHbgF1zw+nojtL988JQ5Z0j5qiCe8B5CcbMCrVoqqpmQgBImHwIZraysnL+"
    "7Jm1tTVhqNpymLHFY9jLJnJYTHNzXZUEUk2FcTIcDpizrJhMJ5Vq0KggiGRApC44dBcYPzfDN8REddPEEEUoc0JE"
    "IQQTEicp5nN6fU2EfDS5verw5tuK5wOVnLjBQLIsA7bUxnWlpgZJTXTWBUhPuPM6b/C/IWlR8xqIyGVZ5kiIQowx"
    "xswVp9ZPnTt3ZtgviSjBPd1mc+BmdwDwPA0NGDP1ykx4nUBm4xjV0l5AJAYivXZ8ae/97FjqDiQ9oDzSDnb8NHW3"
    "wDSqAk54NOyfPn1mbW1tZVACiNHMNHO3G5v6fQJLpMoNsADIcz61vu6yfFbNqkkVmxhVmTvLvqMdo8E5Z6pRg6pl"
    "WbaysjIajc6fO01EbbBfiCC3f0rdzQuAJSAtXngqCmQZra0M+2WxnU1oe+yD16idDXQ3eAI3wqoEMKIRyGVlWayt"
    "rqyurvX7PQa1I78NHxTews0JgBk0agp5tkGA+ewv5+BcRjIkgkbb3NxsfEO0hNFqlpwhS8AiCzhb7EwkoCWfv5Of"
    "4+4GzHvl2yTuEj41tVWb879JTS0rstFwZW1tZWU0KjIxQKOKcJp1t8gKH2cBIAKJ8DI4BzNUwdRmKXqFy9yaqTEw"
    "nU2bpvHeq8YFQ4sIAbY0hI+ZQ2g3vmU8xpuUzA8+in9nhfzf93fNH42pKpEx74xiY2ZVU43OZUSYzzM1x25ldTQY"
    "9tfXT5VFW9VsCpEdwGVKcA8txtft2w5uchbG0myuPS8scOY1Qk0JFEIYb0/H43Hd1MF7NdMYiYiYJY2iadHnyNDW"
    "1S0qY/fsBp0AfLD34aBtWQGLGmAQYREHWNM0xJw5t4Ciy7IsL4p+r3f+/GkiypxjTjgrO0i+aarVbt46zj7AMuPT"
    "XkBuACJgsACFy3JZGfTLqmqmk8msmqUx9KZmplFVVWEWzJhzzKfVi8hiZn1nZhwXW39JJe3kpcgIolGh7Q6gUTMS"
    "JjZEZimKYnV1ZW11texlmbDNMblojoRNu5TnB+Sg35zW0d3MTssSsQtLJuHEJotOFXXtp9PpbDar60Y1eu8XNp+B"
    "o5qBbU77/YFuBzgmJpDtTKwwizUxMXFCoBSRoiiCD2a2furU6upqkbssy5xjtXZ0T7KZ92l4bV3E9sHzcTWB9s/F"
    "2SUAuvu0tOQtwQBVq+tQVbX3zWw2W8iAgqbTegHysvAEUidQJwDHQQCE2eadK6qqqgYtMsmLTERU1QfvxI1Go16v"
    "LMreoF+WmUu1ZAqoQuazfnccyJ1m2iQA80E4LbjlMTeBdhlCil0zGg2wdsTIvI6UGcLU62Vlmala04xms1lT1z4E"
    "r+q9tlOZ5sTMVVV1gaDjQsQEc87tPCFBNRkTqN/vF0WZ51mvV5a5Y3EpPN5ECyEKc5ax8F7whXlL7Qf/fN+vE7zr"
    "HLrnfTWFSVtOtyTM2la/tjuemalaiKjqJkbzvqnquq7qELwP4abwDbsd4IhNIHJOsjxvQULyXIR7/SLLJBc2ZknV"
    "L4qoClDmqIUVRztkw5Zm69COU7Fv7GSKqR/fKBCOZC7OMhTwAo+d7r5Msh2LU1wrELQcDiLaV4pv+0IjNzl1fmf4"
    "xzHeATrq6GRRV4XWUScAHXXUCUBHHXUC0FFHnQB01FEnAB111AlARx11AtBRR50AdNRRJwAdddQJQEcddQLQUUed"
    "AHTUUScAHXXUCUBHHXUC0FFHnQB01FEnAB111AlARx11AtBRR8eb/ncWvPfi1Ru2qAAAAABJRU5ErkJggg=="
)

# --- Interface languages ---------------------------------------------------
UI_LANGUAGES = [("pt", "Português"), ("en", "English")]

# --- Audio language built-ins (code -> whisper --language param) -----------
AUDIO_LANG_OPTIONS = {
    "auto": {"param": None},
    "pt": {"param": "Portuguese"},
    "en": {"param": "English"},
    "es": {"param": "Spanish"},
}
DEFAULT_AUDIO_LANGS = ["auto", "pt", "en", "es"]

# Full Whisper language set (code -> English name). Used by the "Add languages"
# manager. Whisper's --language accepts the English name.
WHISPER_LANGUAGES = {
    "en": "English", "zh": "Chinese", "de": "German", "es": "Spanish",
    "ru": "Russian", "ko": "Korean", "fr": "French", "ja": "Japanese",
    "pt": "Portuguese", "tr": "Turkish", "pl": "Polish", "ca": "Catalan",
    "nl": "Dutch", "ar": "Arabic", "sv": "Swedish", "it": "Italian",
    "id": "Indonesian", "hi": "Hindi", "fi": "Finnish", "vi": "Vietnamese",
    "he": "Hebrew", "uk": "Ukrainian", "el": "Greek", "ms": "Malay",
    "cs": "Czech", "ro": "Romanian", "da": "Danish", "hu": "Hungarian",
    "ta": "Tamil", "no": "Norwegian", "th": "Thai", "ur": "Urdu",
    "hr": "Croatian", "bg": "Bulgarian", "lt": "Lithuanian", "la": "Latin",
    "mi": "Maori", "ml": "Malayalam", "cy": "Welsh", "sk": "Slovak",
    "te": "Telugu", "fa": "Persian", "lv": "Latvian", "bn": "Bengali",
    "sr": "Serbian", "az": "Azerbaijani", "sl": "Slovenian", "kn": "Kannada",
    "et": "Estonian", "mk": "Macedonian", "br": "Breton", "eu": "Basque",
    "is": "Icelandic", "hy": "Armenian", "ne": "Nepali", "mn": "Mongolian",
    "bs": "Bosnian", "kk": "Kazakh", "sq": "Albanian", "sw": "Swahili",
    "gl": "Galician", "mr": "Marathi", "pa": "Punjabi", "si": "Sinhala",
    "km": "Khmer", "sn": "Shona", "yo": "Yoruba", "so": "Somali",
    "af": "Afrikaans", "oc": "Occitan", "ka": "Georgian", "be": "Belarusian",
    "tg": "Tajik", "sd": "Sindhi", "gu": "Gujarati", "am": "Amharic",
    "yi": "Yiddish", "lo": "Lao", "uz": "Uzbek", "fo": "Faroese",
    "ht": "Haitian creole", "ps": "Pashto", "tk": "Turkmen", "nn": "Nynorsk",
    "mt": "Maltese", "sa": "Sanskrit", "lb": "Luxembourgish", "my": "Myanmar",
    "bo": "Tibetan", "tl": "Tagalog", "mg": "Malagasy", "as": "Assamese",
    "tt": "Tatar", "haw": "Hawaiian", "ln": "Lingala", "ha": "Hausa",
    "ba": "Bashkir", "jw": "Javanese", "su": "Sundanese",
}

TASK_KEYS = ["transcribe", "translate"]

# Output formats. 'md' is produced by TranscriptLab (not by whisper directly).
OUTPUT_FORMATS = ["txt", "srt", "vtt", "json", "tsv", "md"]
WHISPER_FORMATS = ["txt", "srt", "vtt", "json", "tsv"]   # produced by whisper
TEXT_REPLACE_FORMATS = ["txt", "srt", "vtt", "tsv", "md"]  # dict find/replace

# Catalog: (cli_name, english_only, size_mb, vram_gb, desc_key)
MODEL_CATALOG = [
    ("tiny",      False, 75,   1, "model_tiny"),
    ("tiny.en",   True,  75,   1, "model_tiny_en"),
    ("base",      False, 145,  1, "model_base"),
    ("base.en",   True,  145,  1, "model_base_en"),
    ("small",     False, 480,  2, "model_small"),
    ("small.en",  True,  480,  2, "model_small_en"),
    ("medium",    False, 1500, 5, "model_medium"),
    ("medium.en", True,  1500, 5, "model_medium_en"),
    ("turbo",     False, 1600, 6, "model_turbo"),
    ("large",     False, 2900, 10, "model_large"),
]
MODEL_INFO = {row[0]: {"english_only": row[1], "size_mb": row[2],
                       "vram_gb": row[3], "desc_key": row[4]}
              for row in MODEL_CATALOG}
ALL_MODEL_CLIS = [row[0] for row in MODEL_CATALOG]

MEDIA_EXTENSIONS = (".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm",
                    ".avi", ".mov", ".flac", ".ogg",
                    ".opus", ".aac", ".wma", ".aiff", ".aif")

# Inputs accepted in the MD File Generation tab (what MarkItDown / our cleaner
# can handle).
MARKITDOWN_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                         ".json", ".xml", ".html", ".htm", ".txt", ".md",
                         ".rtf", ".epub", ".srt", ".vtt")
SUBTITLE_EXTENSIONS = (".srt", ".vtt")

# Download (yt-dlp) options
DOWNLOAD_RESOLUTIONS = ["best", "2160", "1440", "1080", "720", "480", "360"]
DOWNLOAD_AUDIO_FORMATS = ["mp3", "m4a", "opus", "best"]
DOWNLOAD_CONTAINERS = ["mp4", "mkv"]

# Rate-limit caps (Feature G)
TRANSCRIBE_SOFT_CAP = 20
TRANSCRIBE_HARD_CAP = 150
DOWNLOAD_SOFT_CAP = 20
DOWNLOAD_HARD_CAP = 50

# Human-like delays between items (seconds)
YT_TRANSCRIBE_DELAY = (1.5, 3.0)
YT_DOWNLOAD_DELAY = (3.0, 8.0)
BLOCK_BACKOFF_SECONDS = 12.0

# Causes that stop the whole batch after one retry
BLOCK_CAUSES = ("rate_limited", "bot_check")

# Speed-factor (wall/audio) defaults; self-calibrate per Whisper model via a
# capped rolling average persisted across sessions (eta_history.json).
# 1.0 (realtime) was found to badly under-estimate CPU-based Whisper runs
# (e.g. a 2h video taking 8h => factor ~4.0), so the fallback before any real
# sample exists is set conservatively higher and flagged low-confidence.
DEFAULT_SPEED_FACTOR = 3.0
SPEED_FACTOR_SAMPLE_CAP = 20   # rolling-average window; keeps estimate adaptive
YT_PER_VIDEO_DEFAULT = 3.0   # near-constant transcript fetch seconds
MD_PER_FILE_DEFAULT = 0.6    # per-file conversion seconds

ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_ERROR = "error"
ST_SKIPPED = "skipped"
ST_TERMINAL = (ST_DONE, ST_ERROR, ST_SKIPPED)

FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"
# Static ffmpeg build (Windows) used by the auto-download installer.
FFMPEG_WIN_BUILD_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


# ==========================================================================
# Translations
# ==========================================================================

TRANSLATIONS = {
    "pt": {
        "window_title": APP_NAME,
        "tab_transcription": "Transcrição A/V",
        "tab_dictionary": "Dicionário de Vocabulário",
        "tab_md": "Geração de MD",
        # Menubar
        "menu_settings": "Configurações",
        "menu_about": "Sobre",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "MarkItDown...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Formatos de saída...",
        "menu_interface_language": "Idioma da interface",
        # Status indicators (linha 1)
        "dep_whisper": "Whisper",
        "dep_markitdown": "MarkItDown",
        "dep_ffmpeg": "FFmpeg",
        "dep_found": "✓",
        "dep_missing": "✗",
        "dep_hint": "(clique para configurar)",
        # Main controls remaining
        "audio_language": "Idioma do áudio:",
        "ai_model": "Modelo de IA:",
        "add_languages": "Adicionar idiomas...",
        "add_model": "Adicionar modelo...",
        "task": "Tarefa:",
        "vocab_dict": "Dicionário de vocabulário:",
        "none": "(Nenhum)",
        "model_status": "Status do modelo:",
        "no_models_installed": "Nenhum modelo instalado — use 'Adicionar modelo...' para baixar um.",
        "output_folder": "Pasta de saída:",
        "same_folder": "Mesma pasta de cada arquivo",
        "fixed_folder": "Pasta fixa:",
        "browse": "Procurar...",
        # Tasks
        "task_transcribe": "Transcrever (mesmo idioma)",
        "task_translate": "Traduzir para Inglês",
        # Audio langs (built-ins)
        "audlang_auto": "Detectar automaticamente",
        "audlang_portuguese": "Português (PT-BR)",
        "audlang_english": "Inglês (EN)",
        "audlang_spanish": "Espanhol (ES)",
        # Model descriptions
        "model_tiny": "mais rápido, menor precisão",
        "model_tiny_en": "só Inglês, mais rápido",
        "model_base": "rápido, precisão básica",
        "model_base_en": "só Inglês",
        "model_small": "bom equilíbrio velocidade/precisão",
        "model_small_en": "só Inglês",
        "model_medium": "excelente precisão, mais lento",
        "model_medium_en": "só Inglês",
        "model_turbo": "rápido, ótima precisão multilíngue",
        "model_large": "máxima precisão, mais lento e pesado",
        "model_downloaded": "✓ Já baixado no cache  ({size}, ~{vram} GB VRAM recomendado)",
        "model_not_downloaded": "✗ NÃO baixado ainda  ({size} para baixar, ~{vram} GB VRAM recomendado)",
        # Output formats (dialog)
        "output_formats": "Formatos de saída (marque o que deseja manter):",
        "output_formats_title": "Formatos de saída",
        "fmt_txt": "TXT — texto puro, sem marcação de tempo. Ideal para ler/estudar.",
        "fmt_srt": "SRT — legenda com tempos. Use em players de vídeo (YouTube, VLC).",
        "fmt_vtt": "VTT — legenda para web (HTML5). Semelhante ao SRT.",
        "fmt_json": "JSON — dados completos (tempos por palavra/segmento) para uso técnico.",
        "fmt_tsv": "TSV — tabela (início, fim, texto) para abrir em Excel/planilhas.",
        "fmt_md": "MD — transcrição limpa (prosa, sem tempos), ideal para uso com IA.",
        # Queue
        "queue_frame": "Fila de Transcrição",
        "add_files": "+ Adicionar arquivos...",
        "remove_selected": "Remover selecionado",
        "clear_queue": "Limpar fila",
        "move_up": "Mover para cima",
        "move_down": "Mover para baixo",
        "col_order": "#",
        "col_file": "Arquivo",
        "col_folder": "Pasta",
        "col_status": "Status",
        "status_pending": "Pendente",
        "status_running": "Transcrevendo...",
        "status_running_md": "Convertendo...",
        "status_done": "Concluído",
        "status_error": "Erro",
        "status_skipped": "Cancelado",
        # Execution
        "start_batch": "Iniciar Transcrição em Lote",
        "start_batch_md": "Iniciar Conversão em Lote",
        "cancel": "Cancelar",
        "waiting_start": "Aguardando início...",
        "open_output_folder": "Abrir pasta de saída",
        "batch_progress": "Processando {done}/{total}",
        "preparing": "preparando...",
        "elapsed": "decorrido {elapsed}",
        "eta": "ETA {eta}",
        "position": "posição {pos}",
        "batch_finished_label": "Finalizado: {done} concluído(s), {errors} erro(s)",
        # Log
        "log_frame": "Atividade do Whisper (saída em tempo real)",
        "log_frame_md": "Atividade do MarkItDown (saída em tempo real)",
        "log_batch_start": "Lote iniciado em {time}\n",
        "log_batch_end": "\nLote finalizado em {time}\n",
        "log_canceling": "\n[CANCELANDO] Interrompendo após o arquivo atual...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Iniciando: {name}\n{sep}\n",
        "log_probing": "Analisando duração do áudio com ffmpeg...\n",
        "log_duration_ok": "Duração detectada: {dur}\n",
        "log_duration_fail": "Não foi possível detectar a duração (ffmpeg ausente ou formato não lido); a barra mostrará apenas atividade.\n",
        "log_cmd": "Comando: {cmd}\n\n",
        "log_file_done": "\n[OK] Concluído: {name}\n",
        "log_file_error": "\n[ERRO] Falha em {name}: {e}\n",
        "log_dict_warn": "[AVISO] Não foi possível aplicar dicionário em {path}: {e}\n",
        "log_md_make": "Gerando MD limpo a partir da legenda...\n",
        "log_md_markitdown": "Convertendo com MarkItDown: {name}\n",
        "log_download_start": "Iniciando download do modelo '{model}' ({size})...\n",
        "log_download_dest": "Destino: {dest}\n\n",
        "log_model_ok": "\n[OK] Modelo confirmado no cache local.\n",
        # Dialogs / messages
        "warn": "Aviso",
        "error": "Erro",
        "info": "Informação",
        "confirm": "Confirmar",
        "saved": "Salvo",
        "close": "Fechar",
        "err_no_files": "Adicione pelo menos um arquivo à fila.",
        "err_no_whisper": "Whisper não foi encontrado. Abra Configurações → Whisper para localizar ou instalar.",
        "err_no_markitdown": "MarkItDown não foi encontrado. Abra Configurações → MarkItDown para instalá-lo.",
        "err_no_model_selected": "Nenhum modelo de IA instalado/selecionado. Use 'Adicionar modelo...' para baixar um.",
        "err_no_format": "Selecione pelo menos um formato de saída (Configurações → Formatos de saída).",
        "err_no_fixed_dir": "Selecione a pasta de saída fixa ou troque para 'mesma pasta de cada arquivo'.",
        "warn_path_not_found": "O caminho '{path}' não foi encontrado no disco.\nDeseja tentar executar mesmo assim (ex: caso esteja no PATH do sistema)?",
        "warn_queue_locked": "Não é possível editar a fila durante o processamento.",
        "warn_item_locked": "Itens já processados ou em andamento não podem ser removidos/movidos.",
        "info_all_in_queue": "Todos os arquivos selecionados já estão na fila.",
        "dup_dialog_title": "Transcrição já existe",
        "dup_dialog_intro": "{n} arquivo(s) já têm uma transcrição (.md/.srt/.txt/.json) na mesma pasta:",
        "dup_skip_btn": "Não adicionar estes",
        "dup_proceed_btn": "Transcrever mesmo assim",
        "select_media_title": "Selecione um ou mais arquivos de mídia (pode repetir em pastas diferentes)",
        "select_doc_title": "Selecione arquivos para converter em MD",
        "media_files": "Arquivos de mídia",
        "doc_files": "Documentos suportados",
        "all_files": "Todos os arquivos",
        "select_whisper_title": "Selecione o executável do whisper",
        "select_ffmpeg_title": "Selecione o executável do ffmpeg",
        "executable": "Executável",
        "select_output_title": "Selecione a pasta de saída",
        "cancel_title": "Cancelar",
        "cancel_question": "Cancelar o lote? O arquivo atual será interrompido.",
        "exit_title": "Sair",
        "exit_question": "Um processamento está em andamento. Sair mesmo assim?",
        "finished_with_errors_title": "Concluído com erros",
        "finished_with_errors_msg": "{done} arquivo(s) concluídos, {errors} com erro. Veja o log para detalhes.",
        "finished_title": "Concluído",
        "finished_msg": "Todos os {done} arquivo(s) foram processados com sucesso.",
        "ffmpeg_missing_warn": "ffmpeg não foi encontrado. O Whisper precisa dele para ler a maioria dos formatos de áudio/vídeo, então a transcrição pode falhar. Você pode continuar mesmo assim (arquivos .wav às vezes funcionam sem ffmpeg).\n\nDeseja continuar?",
        # Settings: Whisper
        "set_whisper_title": "Configurações — Whisper",
        "set_whisper_exe": "Executável do Whisper:",
        "set_whisper_install": "Instalar Whisper (global)",
        "set_whisper_install_q": "Instalar o Whisper globalmente usando pip?\n\nComando:\n{cmd}\n\nIsto pode baixar vários GB (inclui o PyTorch) e demorar bastante. Continuar?",
        "set_whisper_found": "✓ Whisper encontrado: {path}",
        "set_whisper_missing": "✗ Whisper não encontrado neste computador.",
        "set_models_title": "Modelos de IA (instalados ficam disponíveis no menu principal):",
        "set_models_download": "Baixar modelo selecionado",
        "set_langs_title": "Idiomas do áudio disponíveis no menu principal:",
        "set_lang_add": "Adicionar →",
        "set_lang_remove": "← Remover",
        "set_lang_pick": "Idioma para adicionar:",
        "installed_tag": "  [instalado]",
        "not_installed_tag": "",
        # Settings: MarkItDown
        "set_markitdown_title": "Configurações — MarkItDown",
        "set_markitdown_about": "O MarkItDown converte documentos (PDF, DOCX, etc.) em Markdown. É usado na aba 'Geração de MD'.",
        "set_markitdown_found": "✓ MarkItDown encontrado (interpretador: {py}).",
        "set_markitdown_missing": "✗ MarkItDown não encontrado.",
        "set_markitdown_install": "Instalar MarkItDown (global)",
        "set_markitdown_install_q": "Instalar o MarkItDown globalmente usando pip?\n\nComando:\n{cmd}\n\nContinuar?",
        "set_recheck": "Verificar novamente",
        # Settings: FFmpeg
        "set_ffmpeg_title": "Configurações — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg encontrado: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg não encontrado.",
        "ffmpeg_locate": "Localizar...",
        "ffmpeg_open_folder": "Abrir pasta",
        "set_ffmpeg_install_auto": "Baixar e instalar automaticamente",
        "set_ffmpeg_winget": "Instalar via winget",
        "set_ffmpeg_open_page": "Abrir página de download",
        "set_ffmpeg_auto_q": "Baixar uma versão pronta do ffmpeg e instalá-la em:\n{dest}\n\nIsto baixa ~80 MB. Continuar?",
        "set_ffmpeg_downloading": "Baixando ffmpeg... aguarde.\n",
        "set_ffmpeg_extracting": "Extraindo...\n",
        "set_ffmpeg_done": "✓ FFmpeg instalado em: {path}\n",
        "set_ffmpeg_fail": "✗ Falha ao instalar o ffmpeg automaticamente: {e}\nUse 'Abrir página de download' para instalar manualmente.\n",
        # Settings: interface language
        "lang_english": "English",
        "lang_portuguese": "Português",
        # Install (generic)
        "install_running": "Executando, acompanhe abaixo...\n",
        "install_done_ok": "\n[OK] Concluído com sucesso.\n",
        "install_done_fail": "\n[ERRO] O processo terminou com código {code}.\n",
        "install_log_title": "Saída:",
        # About
        "about_title": "Sobre o TranscriptLab",
        "about_version": "Versão",
        "about_author": "Autor",
        "about_contact": "Contato",
        # Dictionaries
        "saved_profiles": "Perfis salvos:",
        "new": "Novo",
        "duplicate": "Duplicar",
        "delete": "Excluir",
        "edit_profile": "Editar Perfil",
        "profile_name": "Nome do perfil:",
        "priming_help": ("Texto de priming (--initial_prompt)\n"
                         "Uma frase curta e natural com os nomes próprios e termos técnicos escritos "
                         "exatamente como devem aparecer. O Whisper usa isso como uma \"dica\" para "
                         "grafar esses termos corretamente desde o começo.\n"
                         "Exemplo: A Dra. Ana Costa explica a fotossíntese, as mitocôndrias e o ciclo de Krebs."),
        "replacements_help": ("Substituições pós-transcrição (uma por linha, formato:  errado=correto)\n"
                              "Correções automáticas aplicadas DEPOIS que o Whisper termina, direto nos arquivos de "
                              "texto. Úteis para erros que se repetem sempre. Diferencia maiúsculas de minúsculas.\n"
                              "Exemplo: ciclo de crebs=ciclo de Krebs"),
        "save_profile": "Salvar Perfil",
        "dup_title": "Duplicar Perfil",
        "dup_prompt": "Nome do novo perfil:",
        "dup_suffix": " (cópia)",
        "err_dup_exists": "Já existe um perfil com esse nome.",
        "select_to_duplicate": "Selecione um perfil para duplicar.",
        "delete_question": "Excluir o perfil '{name}'?",
        "err_no_profile_name": "Dê um nome ao perfil antes de salvar.",
        "profile_saved_msg": "Perfil '{name}' salvo com sucesso.",
        # Clipping
        "clip_frame": "Transcrever apenas um trecho (opcional)",
        "clip_enable": "Transcrever somente de um ponto a outro do vídeo/áudio",
        "clip_start": "Início:",
        "clip_end": "Fim:",
        "clip_hint": "Formato H:MM:SS (ex.: 0:05:00 = 5 minutos). Deixe a caixa desmarcada para processar o arquivo inteiro.",
        "clip_needs_ffmpeg": "Este recurso precisa do ffmpeg (usado para cortar o trecho antes de transcrever). Instale o ffmpeg em Configurações → FFmpeg para habilitá-lo.",
        "err_clip_invalid": "Verifique os campos de início/fim do trecho. Use o formato H:MM:SS e garanta que o fim seja depois do início.",
        "err_clip_needs_ffmpeg": "O recorte de trecho está marcado, mas o ffmpeg não foi encontrado. Instale o ffmpeg ou desmarque essa opção.",
        "phase_preparing": "Carregando modelo e preparando o áudio... isso pode levar alguns minutos (a barra ficará completa quando a transcrição real começar).",
        "phase_transcribing_note": "Transcrevendo...",
        "partial_output_note": "Um arquivo '*.partial.txt' está sendo salvo continuamente nesta pasta como rede de segurança, caso o processo seja interrompido.",
        # MD tab
        "md_intro": "Converta documentos (PDF, DOCX, TXT, SRT, etc.) em Markdown limpo, pronto para uso com IA. Legendas (SRT/VTT) viram prosa sem marcações de tempo.",
        "md_queue_frame": "Fila de Conversão",
    },
    "en": {
        "window_title": APP_NAME,
        "tab_transcription": "A/V Transcription",
        "tab_dictionary": "Vocabulary Dictionary",
        "tab_md": "MD File Generation",
        "menu_settings": "Settings",
        "menu_about": "About",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "MarkItDown...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Output formats...",
        "menu_interface_language": "Interface language",
        "dep_whisper": "Whisper",
        "dep_markitdown": "MarkItDown",
        "dep_ffmpeg": "FFmpeg",
        "dep_found": "✓",
        "dep_missing": "✗",
        "dep_hint": "(click to configure)",
        "audio_language": "Audio language:",
        "ai_model": "AI model:",
        "add_languages": "Add languages...",
        "add_model": "Add model...",
        "task": "Task:",
        "vocab_dict": "Vocabulary dictionary:",
        "none": "(None)",
        "model_status": "Model status:",
        "no_models_installed": "No models installed — use 'Add model...' to download one.",
        "output_folder": "Output folder:",
        "same_folder": "Same folder as each file",
        "fixed_folder": "Fixed folder:",
        "browse": "Browse...",
        "task_transcribe": "Transcribe (same language)",
        "task_translate": "Translate to English",
        "audlang_auto": "Auto-detect",
        "audlang_portuguese": "Portuguese (PT-BR)",
        "audlang_english": "English (EN)",
        "audlang_spanish": "Spanish (ES)",
        "model_tiny": "fastest, lowest accuracy",
        "model_tiny_en": "English only, fastest",
        "model_base": "fast, basic accuracy",
        "model_base_en": "English only",
        "model_small": "good speed/accuracy balance",
        "model_small_en": "English only",
        "model_medium": "excellent accuracy, slower",
        "model_medium_en": "English only",
        "model_turbo": "fast, great multilingual accuracy",
        "model_large": "maximum accuracy, slowest and heaviest",
        "model_downloaded": "✓ Already in cache  ({size}, ~{vram} GB VRAM recommended)",
        "model_not_downloaded": "✗ NOT downloaded yet  ({size} to download, ~{vram} GB VRAM recommended)",
        "output_formats": "Output formats (check what you want to keep):",
        "output_formats_title": "Output formats",
        "fmt_txt": "TXT — plain text, no timestamps. Best for reading/studying.",
        "fmt_srt": "SRT — subtitles with timing. Use in video players (YouTube, VLC).",
        "fmt_vtt": "VTT — web subtitles (HTML5). Similar to SRT.",
        "fmt_json": "JSON — full data (per-word/segment timing) for technical use.",
        "fmt_tsv": "TSV — table (start, end, text) to open in Excel/spreadsheets.",
        "fmt_md": "MD — clean transcript (prose, no timestamps), best for AI use.",
        "queue_frame": "Transcription Queue",
        "add_files": "+ Add files...",
        "remove_selected": "Remove selected",
        "clear_queue": "Clear queue",
        "move_up": "Move up",
        "move_down": "Move down",
        "col_order": "#",
        "col_file": "File",
        "col_folder": "Folder",
        "col_status": "Status",
        "status_pending": "Pending",
        "status_running": "Transcribing...",
        "status_running_md": "Converting...",
        "status_done": "Done",
        "status_error": "Error",
        "status_skipped": "Canceled",
        "start_batch": "Start Batch Transcription",
        "start_batch_md": "Start Batch Conversion",
        "cancel": "Cancel",
        "waiting_start": "Waiting to start...",
        "open_output_folder": "Open output folder",
        "batch_progress": "Processing {done}/{total}",
        "preparing": "preparing...",
        "elapsed": "elapsed {elapsed}",
        "eta": "ETA {eta}",
        "position": "position {pos}",
        "batch_finished_label": "Finished: {done} done, {errors} error(s)",
        "log_frame": "Whisper Activity (real-time output)",
        "log_frame_md": "MarkItDown Activity (real-time output)",
        "log_batch_start": "Batch started at {time}\n",
        "log_batch_end": "\nBatch finished at {time}\n",
        "log_canceling": "\n[CANCELING] Stopping after the current file...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Starting: {name}\n{sep}\n",
        "log_probing": "Probing audio duration with ffmpeg...\n",
        "log_duration_ok": "Detected duration: {dur}\n",
        "log_duration_fail": "Could not detect duration (ffmpeg missing or format unreadable); the bar will show activity only.\n",
        "log_cmd": "Command: {cmd}\n\n",
        "log_file_done": "\n[OK] Finished: {name}\n",
        "log_file_error": "\n[ERROR] Failed on {name}: {e}\n",
        "log_dict_warn": "[WARNING] Could not apply dictionary to {path}: {e}\n",
        "log_md_make": "Generating clean MD from the subtitle...\n",
        "log_md_markitdown": "Converting with MarkItDown: {name}\n",
        "log_download_start": "Starting download of model '{model}' ({size})...\n",
        "log_download_dest": "Destination: {dest}\n\n",
        "log_model_ok": "\n[OK] Model confirmed in local cache.\n",
        "warn": "Warning",
        "error": "Error",
        "info": "Information",
        "confirm": "Confirm",
        "saved": "Saved",
        "close": "Close",
        "err_no_files": "Add at least one file to the queue.",
        "err_no_whisper": "Whisper was not found. Open Settings → Whisper to locate or install it.",
        "err_no_markitdown": "MarkItDown was not found. Open Settings → MarkItDown to install it.",
        "err_no_model_selected": "No AI model installed/selected. Use 'Add model...' to download one.",
        "err_no_format": "Select at least one output format (Settings → Output formats).",
        "err_no_fixed_dir": "Select the fixed output folder or switch to 'same folder as each file'.",
        "warn_path_not_found": "The path '{path}' was not found on disk.\nDo you want to try running it anyway (e.g. if it's on the system PATH)?",
        "warn_queue_locked": "The queue cannot be edited during processing.",
        "warn_item_locked": "Items already processed or in progress can't be removed/moved.",
        "info_all_in_queue": "All selected files are already in the queue.",
        "dup_dialog_title": "Transcript already exists",
        "dup_dialog_intro": "{n} file(s) already have a transcript (.md/.srt/.txt/.json) in the same folder:",
        "dup_skip_btn": "Don't add these",
        "dup_proceed_btn": "Transcribe anyway",
        "select_media_title": "Select one or more media files (you can repeat across folders)",
        "select_doc_title": "Select files to convert to MD",
        "media_files": "Media files",
        "doc_files": "Supported documents",
        "all_files": "All files",
        "select_whisper_title": "Select the whisper executable",
        "select_ffmpeg_title": "Select the ffmpeg executable",
        "executable": "Executable",
        "select_output_title": "Select the output folder",
        "cancel_title": "Cancel",
        "cancel_question": "Cancel the batch? The current file will be interrupted.",
        "exit_title": "Exit",
        "exit_question": "Processing is in progress. Exit anyway?",
        "finished_with_errors_title": "Finished with errors",
        "finished_with_errors_msg": "{done} file(s) finished, {errors} with error. See the log for details.",
        "finished_title": "Finished",
        "finished_msg": "All {done} file(s) were processed successfully.",
        "ffmpeg_missing_warn": "ffmpeg was not found. Whisper needs it to read most audio/video formats, so transcription may fail. You can continue anyway (.wav files sometimes work without ffmpeg).\n\nContinue?",
        "set_whisper_title": "Settings — Whisper",
        "set_whisper_exe": "Whisper executable:",
        "set_whisper_install": "Install Whisper (global)",
        "set_whisper_install_q": "Install Whisper globally using pip?\n\nCommand:\n{cmd}\n\nThis may download several GB (includes PyTorch) and take a while. Continue?",
        "set_whisper_found": "✓ Whisper found: {path}",
        "set_whisper_missing": "✗ Whisper not found on this computer.",
        "set_models_title": "AI models (installed ones appear in the main menu):",
        "set_models_download": "Download selected model",
        "set_langs_title": "Audio languages available in the main menu:",
        "set_lang_add": "Add →",
        "set_lang_remove": "← Remove",
        "set_lang_pick": "Language to add:",
        "installed_tag": "  [installed]",
        "not_installed_tag": "",
        "set_markitdown_title": "Settings — MarkItDown",
        "set_markitdown_about": "MarkItDown converts documents (PDF, DOCX, etc.) into Markdown. It is used in the 'MD File Generation' tab.",
        "set_markitdown_found": "✓ MarkItDown found (interpreter: {py}).",
        "set_markitdown_missing": "✗ MarkItDown not found.",
        "set_markitdown_install": "Install MarkItDown (global)",
        "set_markitdown_install_q": "Install MarkItDown globally using pip?\n\nCommand:\n{cmd}\n\nContinue?",
        "set_recheck": "Re-check",
        "set_ffmpeg_title": "Settings — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg found: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg not found.",
        "ffmpeg_locate": "Locate...",
        "ffmpeg_open_folder": "Open folder",
        "set_ffmpeg_install_auto": "Download and install automatically",
        "set_ffmpeg_winget": "Install via winget",
        "set_ffmpeg_open_page": "Open download page",
        "set_ffmpeg_auto_q": "Download a ready-made ffmpeg build and install it to:\n{dest}\n\nThis downloads ~80 MB. Continue?",
        "set_ffmpeg_downloading": "Downloading ffmpeg... please wait.\n",
        "set_ffmpeg_extracting": "Extracting...\n",
        "set_ffmpeg_done": "✓ FFmpeg installed at: {path}\n",
        "set_ffmpeg_fail": "✗ Could not auto-install ffmpeg: {e}\nUse 'Open download page' to install it manually.\n",
        "lang_english": "English",
        "lang_portuguese": "Português",
        "install_running": "Running, follow below...\n",
        "install_done_ok": "\n[OK] Completed successfully.\n",
        "install_done_fail": "\n[ERROR] Process ended with code {code}.\n",
        "install_log_title": "Output:",
        "about_title": "About TranscriptLab",
        "about_version": "Version",
        "about_author": "Author",
        "about_contact": "Contact",
        "saved_profiles": "Saved profiles:",
        "new": "New",
        "duplicate": "Duplicate",
        "delete": "Delete",
        "edit_profile": "Edit Profile",
        "profile_name": "Profile name:",
        "priming_help": ("Priming text (--initial_prompt)\n"
                         "A short, natural sentence with the proper names and technical terms written "
                         "exactly as they should appear. Whisper uses this as a \"hint\" to spell those "
                         "terms correctly from the start.\n"
                         "Example: Dr. Ana Costa explains photosynthesis, mitochondria and the Krebs cycle."),
        "replacements_help": ("Post-transcription replacements (one per line, format:  wrong=correct)\n"
                              "Automatic corrections applied AFTER Whisper finishes, directly in the text files. "
                              "Useful for errors that repeat every time. Case-sensitive.\n"
                              "Example: krebs cycle=Krebs cycle"),
        "save_profile": "Save Profile",
        "dup_title": "Duplicate Profile",
        "dup_prompt": "New profile name:",
        "dup_suffix": " (copy)",
        "err_dup_exists": "A profile with that name already exists.",
        "select_to_duplicate": "Select a profile to duplicate.",
        "delete_question": "Delete the profile '{name}'?",
        "err_no_profile_name": "Give the profile a name before saving.",
        "profile_saved_msg": "Profile '{name}' saved successfully.",
        "clip_frame": "Transcribe only part of the file (optional)",
        "clip_enable": "Transcribe only from one point to another in the video/audio",
        "clip_start": "Start:",
        "clip_end": "End:",
        "clip_hint": "Format H:MM:SS (e.g. 0:05:00 = 5 minutes). Leave unchecked to process the whole file.",
        "clip_needs_ffmpeg": "This feature needs ffmpeg (used to cut the segment before transcribing). Install ffmpeg in Settings → FFmpeg to enable it.",
        "err_clip_invalid": "Check the start/end fields. Use the H:MM:SS format and make sure the end is after the start.",
        "err_clip_needs_ffmpeg": "Time-range clipping is checked, but ffmpeg was not found. Install ffmpeg or uncheck this option.",
        "phase_preparing": "Loading the model and preparing the audio... this can take a few minutes (the bar will fill in once real transcription starts).",
        "phase_transcribing_note": "Transcribing...",
        "partial_output_note": "A '*.partial.txt' file is being saved continuously in this folder as a safety net in case the process is interrupted.",
        "md_intro": "Convert documents (PDF, DOCX, TXT, SRT, etc.) into clean Markdown, ready for AI use. Subtitles (SRT/VTT) become prose with no timestamps.",
        "md_queue_frame": "Conversion Queue",
    },
}

# --- YouTube tab strings (merged in to keep the main table readable) -------
TRANSLATIONS["pt"].update({
    "tab_youtube": "Transcrição do YouTube",
    "yt_intro": "Cole um ou vários links do YouTube. O app baixa a transcrição/legenda pública de cada vídeo e gera um arquivo Markdown limpo.",
    "yt_output_info": "Este processo gera arquivos .md.",
    "yt_settings_note": "Os arquivos .srt e .txt são opcionais (marque abaixo). As opções de 'Formatos de saída' das Configurações NÃO se aplicam aqui.",
    "yt_md_required_note": "O MarkItDown é necessário para esta aba. Clique no indicador acima para instalá-lo.",
    "yt_pref_lang": "Idioma preferido da transcrição:",
    "yt_lang_auto": "Automático (melhor disponível)",
    "yt_links_label": "Cole um ou mais links do YouTube (um por linha):",
    "yt_add_links": "Adicionar à fila",
    "yt_clear_input": "Limpar campo",
    "yt_col_video": "Vídeo",
    "status_running_yt": "Baixando...",
    "yt_keep_srt": "Salvar também .srt (legenda com tempos)",
    "yt_keep_txt": "Salvar também .txt (texto puro)",
    "yt_no_valid_links": "Nenhum link do YouTube válido foi encontrado.",
    "yt_some_invalid": "{n} linha(s) ignorada(s) por não serem links válidos do YouTube.",
    "yt_need_output_dir": "Escolha primeiro uma pasta de saída.",
    "yt_log_frame": "Atividade do YouTube (saída em tempo real)",
    "yt_start": "Iniciar Download das Transcrições",
    "yt_log_fetch": "Buscando transcrição de {vid}...\n",
    "yt_generated_suffix": " (gerada automaticamente)",
    "yt_log_lang_used": "Idioma da transcrição usada: {lang}{gen}\n",
    "yt_log_lang_mismatch": "O idioma pedido ('{want}') não está disponível; foi usado '{got}'. Disponíveis: {avail}\n",
    "yt_log_wrote": "Salvo: {files}\n",
    "yt_err_no_transcript": "Este vídeo não tem legenda/transcrição disponível para baixar.",
    "yt_err_unavailable": "Vídeo indisponível, privado ou removido.",
    "yt_err_restricted": "Vídeo restrito (idade/região/membros); não é possível obter a transcrição.",
    "yt_err_blocked": "O YouTube bloqueou as requisições temporariamente. Aguarde um pouco ou adicione menos links de cada vez.",
    "yt_err_no_connection": "Sem conexão com o YouTube.",
    "yt_err_engine_missing": "O MarkItDown (e seu mecanismo do YouTube) não está instalado.",
    "yt_err_generic": "Não foi possível obter a transcrição: {e}",
})
TRANSLATIONS["en"].update({
    "tab_youtube": "YouTube Transcription",
    "yt_intro": "Paste one or several YouTube links. The app downloads each video's public transcript/subtitles and produces a clean Markdown file, ready for AI use.",
    "yt_output_info": "This process always outputs the .md file. The .srt and .txt files are optional (check below).",
    "yt_settings_note": "The 'Output formats' settings do NOT apply to this tab.",
    "yt_md_required_note": "MarkItDown is required for this tab. Click the indicator above to install it.",
    "yt_pref_lang": "Preferred transcript language:",
    "yt_lang_auto": "Auto (best available)",
    "yt_links_label": "Paste one or more YouTube links (one per line):",
    "yt_add_links": "Add to queue",
    "yt_clear_input": "Clear box",
    "yt_col_video": "Video",
    "status_running_yt": "Downloading...",
    "yt_keep_srt": "Also save .srt (subtitles with timing)",
    "yt_keep_txt": "Also save .txt (plain text)",
    "yt_no_valid_links": "No valid YouTube links were found.",
    "yt_some_invalid": "{n} line(s) ignored (not valid YouTube links).",
    "yt_need_output_dir": "Choose an output folder first.",
    "yt_log_frame": "YouTube Activity (real-time output)",
    "yt_start": "Start Transcript Download",
    "yt_log_fetch": "Fetching transcript for {vid}...\n",
    "yt_generated_suffix": " (auto-generated)",
    "yt_log_lang_used": "Transcript language used: {lang}{gen}\n",
    "yt_log_lang_mismatch": "Requested language ('{want}') is not available; used '{got}'. Available: {avail}\n",
    "yt_log_wrote": "Saved: {files}\n",
    "yt_err_no_transcript": "This video has no subtitles/transcript available to download.",
    "yt_err_unavailable": "Video unavailable, private, or removed.",
    "yt_err_restricted": "Restricted video (age/region/members); transcript can't be retrieved.",
    "yt_err_blocked": "YouTube temporarily blocked requests. Wait a bit, or add fewer links at once.",
    "yt_err_no_connection": "No connection to YouTube.",
    "yt_err_engine_missing": "MarkItDown (and its YouTube engine) is not installed.",
    "yt_err_generic": "Could not get the transcript: {e}",
})

# --- v0.8.0 additions ------------------------------------------------------
TRANSLATIONS["pt"].update({
    "tab_download": "Download do YouTube",
    # dependency indicators / menu / settings
    "dep_ytdlp": "yt-dlp",
    "menu_ytdlp": "yt-dlp...",
    "set_ytdlp_title": "Configurações do yt-dlp",
    "set_ytdlp_about": "O yt-dlp expande playlists e baixa vídeos/áudio do YouTube. "
                       "Links de vídeo único para transcrição funcionam sem ele.",
    "set_ytdlp_found": "yt-dlp encontrado e disponível.",
    "set_ytdlp_missing": "yt-dlp não encontrado. Clique em Instalar.",
    "set_ytdlp_install": "Instalar / Atualizar yt-dlp",
    "set_ytdlp_install_q": "Executar:\n\n{cmd}\n\nContinuar?",
    # Feature C status / summary
    "status_cur_pos": "Posição do Vídeo Atual: {pos}",
    "status_total_transcribed": "Total Transcrito: {val}",
    "status_eta_complete": "Tempo Estimado para Concluir: {eta}",
    "eta_low_confidence_suffix": "(estimativa inicial)",
    "pct_label": "{pct}%",
    "col_length": "Duração",
    "md_col_size": "Tamanho",
    "summary_videos": "Total de Vídeos: {n}",
    "summary_total_len": "Duração Total: {dur}",
    "summary_est_transcribe": "Tempo Estimado para Transcrever: {eta}",
    "summary_est_download": "Tempo Estimado para Baixar: {eta}",
    "summary_files": "Total de Arquivos: {n}",
    "summary_total_size": "Tamanho Total: {size}",
    "summary_est_convert": "Tempo Estimado para Converter: {eta}",
    "summary_unknown_hint": "(durações desconhecidas — instale o FFmpeg/yt-dlp)",
    "est_approx_note": "≈ aproximado",
    "queue_count_near": "Na fila: {n}",
    # playlist expansion
    "yt_log_fetching_playlist": "Expandindo playlist...\n",
    "yt_playlist_mix_rejected": "Playlists do tipo \"Mix\"/rádio (infinitas) não são suportadas.",
    "yt_playlist_empty": "A playlist está vazia ou indisponível.",
    "yt_playlist_added": "{n} vídeo(s) adicionado(s) da playlist.",
    "yt_expand_error": "Não foi possível expandir a playlist: {e}",
    "yt_need_ytdlp_playlist": "Links de playlist exigem o yt-dlp. Abra Configurações → yt-dlp para instalá-lo.",
    "yt_expanding": "Expandindo playlist, aguarde...",
    # caps
    "cap_soft_title": "Aviso: muitos vídeos",
    "cap_soft_q": "Você tem {n} vídeos na fila. O YouTube pode bloquear temporariamente seu IP "
                  "por excesso de requisições quando muitos vídeos são processados em sequência.\n\n"
                  "Deseja iniciar mesmo assim?",
    "cap_soft_ok": "OK, pode iniciar",
    "cap_soft_cancel": "Cancelar",
    "cap_hard_title": "Lote acima do limite",
    "cap_hard_msg": "O lote tem {n} vídeos; o máximo é {max}. Divida em lotes menores.",
    # rate-limit
    "yt_log_backoff": "Sinal de bloqueio detectado. Aguardando antes de tentar novamente...\n",
    "yt_log_batch_stopped": "Lote interrompido para evitar bloqueio do IP. Itens restantes não processados.\n",
    "yt_block_title": "YouTube bloqueou temporariamente",
    "yt_block_dialog": "O YouTube bloqueou temporariamente seu IP (muitas requisições). "
                       "Aguarde ~24–48h, reduza o lote, aumente o atraso ou tente mais tarde.",
    # MD metadata header
    "yt_md_name": "Nome do Vídeo",
    "yt_md_duration": "Duração do Vídeo",
    "yt_md_date": "Data",
    "yt_md_link": "Link",
    "yt_md_unknown": "Desconhecido",
    # cause messages + actions
    "yt_cause_no_transcript": "Sem legenda/transcrição disponível.",
    "yt_cause_no_transcript_action": "Se isso ocorrer em muitos vídeos de uma vez, seu IP pode estar limitado.",
    "yt_cause_members": "Vídeo exclusivo para membros — exige assinatura do canal.",
    "yt_cause_private": "Vídeo privado.",
    "yt_cause_unavailable": "Vídeo indisponível, privado ou removido.",
    "yt_cause_age": "Restrito por idade; não é possível obter sem login.",
    "yt_cause_geo": "Não disponível na sua região.",
    "yt_cause_rate": "O YouTube bloqueou temporariamente seu IP (muitas requisições).",
    "yt_cause_rate_action": "Aguarde ~24–48h, reduza o lote ou aumente o atraso.",
    "yt_cause_bot": "A verificação anti-robô do YouTube está bloqueando.",
    "yt_cause_bot_action": "Atualize o yt-dlp ou tente mais tarde.",
    "yt_cause_format": "A resolução escolhida não está disponível para este vídeo.",
    "yt_cause_format_action": "Tente \"Melhor\" ou uma resolução menor.",
    "yt_cause_live": "Vídeo ao vivo/futuro, sem conteúdo para baixar ainda.",
    "yt_cause_no_conn": "Sem conexão com o YouTube.",
    "yt_cause_engine": "O mecanismo do YouTube não está instalado.",
    "yt_cause_generic": "Não foi possível concluir: {e}",
    # Download tab
    "dl_intro": "Cole links de vídeos ou de playlists do YouTube e baixe o vídeo ou apenas o áudio. "
                "Você é responsável por respeitar os termos do site e os direitos autorais.",
    "dl_resolution": "Resolução:",
    "dl_res_best": "Melhor",
    "dl_audio_only": "Apenas áudio",
    "dl_audio_format": "Formato de áudio:",
    "dl_container": "Contêiner de vídeo:",
    "dl_start": "Iniciar Download",
    "dl_log_frame": "Atividade do Download (saída em tempo real)",
    "dl_need_output_dir": "Escolha primeiro uma pasta de saída.",
    "dl_need_ytdlp": "O yt-dlp é necessário para baixar. Clique no indicador acima para instalá-lo.",
    "dl_ffmpeg_note": "O FFmpeg é necessário para mesclar vídeo+áudio e extrair áudio.",
    "dl_ffmpeg_nudge_q": "O FFmpeg não foi encontrado. Sem ele, só é possível baixar formatos progressivos "
                         "(resolução menor, sem extração de áudio). Deseja continuar mesmo assim?",
    "dl_links_label": "Cole links de vídeos ou playlists (um por linha):",
    "status_running_dl": "Baixando...",
    "dl_queue_frame": "Fila de Download",
    "dl_options": "Opções de download",
    "btn_add": "+Adicionar",
    "add_dialog_title": "Adicionar links do YouTube",
    "add_dialog_info": "Cole um ou mais links do YouTube, um por linha.\n"
                       "Você também pode colar o link de uma playlist — o aplicativo "
                       "carregará automaticamente os links dos vídeos individuais.",
})
TRANSLATIONS["pt"].update({
    # v0.9.0
    "yt_queue_frame": "Fila de Transcrição do YouTube",
    "save": "Salvar",
    "status_transcribing": "Transcrevendo...",
    "pause_every": "Pausar a cada",
    "pause_videos_for": "vídeos por",
    "pause_minutes": "minutos",
    "pause_log_start": "Pausa de {m} min após {n} vídeos (proteção contra bloqueio)...\n",
    "pause_log_tick": "  ...retomando em ~{m} min\n",
    "pause_log_resume": "Retomando.\n",
    "dl_transcribe_after": "Transcrever o vídeo após o download",
    "dl_define_whisper": "Definir Configurações do Whisper",
    "dl_whisper_intro": "Escolha o modelo, o idioma do áudio e o dicionário de vocabulário "
                        "que serão usados para transcrever os vídeos baixados. Os formatos de "
                        "saída (MD/SRT/TXT/JSON...) seguem as Configurações → Formatos de saída.",
    "dl_need_whisper": "O Whisper não foi encontrado. Abra Configurações → Whisper para localizá-lo ou instalá-lo.",
    "dl_transcribe_needs_ffmpeg": "O FFmpeg é necessário para a transcrição. Instale o FFmpeg e tente novamente.",
    "dl_whisper_not_defined": "Antes de iniciar, clique em \"Definir Configurações do Whisper\" e "
                              "escolha um modelo (instalado), o idioma do áudio e o dicionário.",
    "dl_transcribe_start": "Transcrevendo {name}...\n",
    "dl_transcribe_done": "Transcrição concluída.\n",
    "dl_transcribe_error": "[AVISO] Falha na transcrição: {e}\n",
    "dl_transcribe_no_file": "[AVISO] Não foi possível localizar o arquivo baixado para transcrever.\n",
    # grabber tab
    "tab_grabber": "Coletor de Links (Playlist do YouTube)",
    "grab_intro": "Cole um ou mais links de playlists OU de canais/@handles do YouTube "
                  "(um por linha). O aplicativo retorna os links dos vídeos individuais.",
    "grab_input_label": "Playlists / canais (um por linha)",
    "grab_btn": "Coletar links",
    "grab_clear": "Limpar",
    "grab_mode_title_link": "Título + link",
    "grab_mode_link_only": "Somente link",
    "grab_output_label": "Vídeos encontrados",
    "grab_copy": "Copiar tudo",
    "grab_save": "Salvar em .txt",
    "grab_need_ytdlp": "O yt-dlp é necessário para esta aba. Abra Configurações → yt-dlp para instalá-lo.",
    "grab_no_input": "Cole pelo menos um link de playlist ou canal.",
    "grab_working": "Coletando links...",
    "grab_done_msg": "{n} vídeo(s) encontrado(s).",
    "grab_empty": "Nenhum vídeo encontrado.",
    "grab_error": "Falha ao coletar os links.",
    "grab_copied": "Copiado para a área de transferência.",
    "grab_saved": "Salvo em {path}",
    "grab_fetching": "Lendo: {url}",
    "grab_channel_sub": "  sublista: {name}",
    "dl_summary_transcribe_note": "+ transcrição após cada download",
})
TRANSLATIONS["en"].update({
    "tab_download": "YouTube Download",
    "dep_ytdlp": "yt-dlp",
    "menu_ytdlp": "yt-dlp...",
    "set_ytdlp_title": "yt-dlp Settings",
    "set_ytdlp_about": "yt-dlp expands playlists and downloads YouTube video/audio. "
                       "Single-video transcript links work without it.",
    "set_ytdlp_found": "yt-dlp found and available.",
    "set_ytdlp_missing": "yt-dlp not found. Click Install.",
    "set_ytdlp_install": "Install / Update yt-dlp",
    "set_ytdlp_install_q": "Run:\n\n{cmd}\n\nContinue?",
    "status_cur_pos": "Current Video Position: {pos}",
    "status_total_transcribed": "Total Transcribed: {val}",
    "status_eta_complete": "Estimated Time to Complete: {eta}",
    "eta_low_confidence_suffix": "(initial estimate)",
    "pct_label": "{pct}%",
    "col_length": "Length",
    "md_col_size": "Size",
    "summary_videos": "Total Videos: {n}",
    "summary_total_len": "Total Length: {dur}",
    "summary_est_transcribe": "Estimated Time to Transcribe: {eta}",
    "summary_est_download": "Estimated Time to Download: {eta}",
    "summary_files": "Total Files: {n}",
    "summary_total_size": "Total Size: {size}",
    "summary_est_convert": "Estimated Time to Convert: {eta}",
    "summary_unknown_hint": "(durations unknown — install FFmpeg/yt-dlp)",
    "est_approx_note": "≈ approximate",
    "queue_count_near": "In queue: {n}",
    "yt_log_fetching_playlist": "Expanding playlist...\n",
    "yt_playlist_mix_rejected": "Endless \"Mix\"/radio playlists are not supported.",
    "yt_playlist_empty": "The playlist is empty or unavailable.",
    "yt_playlist_added": "{n} video(s) added from the playlist.",
    "yt_expand_error": "Could not expand the playlist: {e}",
    "yt_need_ytdlp_playlist": "Playlist links require yt-dlp. Open Settings → yt-dlp to install it.",
    "yt_expanding": "Expanding playlist, please wait...",
    "cap_soft_title": "Warning: many videos",
    "cap_soft_q": "You have {n} videos in the queue. YouTube may temporarily block your IP "
                  "for too many requests when many videos are processed in a row.\n\n"
                  "Do you want to start anyway?",
    "cap_soft_ok": "OK, Do it",
    "cap_soft_cancel": "Cancel",
    "cap_hard_title": "Batch over the limit",
    "cap_hard_msg": "The batch has {n} videos; the maximum is {max}. Please split into smaller batches.",
    "yt_log_backoff": "Block signal detected. Waiting before one retry...\n",
    "yt_log_batch_stopped": "Batch stopped to avoid an IP block. Remaining items left unprocessed.\n",
    "yt_block_title": "YouTube temporarily blocked",
    "yt_block_dialog": "YouTube temporarily blocked your IP (too many requests). "
                       "Wait ~24–48h, reduce the batch, increase the delay, or try later.",
    "yt_md_name": "Video Name",
    "yt_md_duration": "Video Duration",
    "yt_md_date": "Date",
    "yt_md_link": "Link",
    "yt_md_unknown": "Unknown",
    "yt_cause_no_transcript": "No subtitles/transcript available.",
    "yt_cause_no_transcript_action": "If this fires for many videos at once, your IP may be rate-limited.",
    "yt_cause_members": "Members-only video — requires channel membership.",
    "yt_cause_private": "Private video.",
    "yt_cause_unavailable": "Video unavailable, private, or removed.",
    "yt_cause_age": "Age-restricted; can't be retrieved without sign-in.",
    "yt_cause_geo": "Not available in your region.",
    "yt_cause_rate": "YouTube temporarily blocked your IP (too many requests).",
    "yt_cause_rate_action": "Wait ~24–48h, reduce the batch, or increase the delay.",
    "yt_cause_bot": "YouTube's bot-check is blocking this.",
    "yt_cause_bot_action": "Update yt-dlp or try again later.",
    "yt_cause_format": "The chosen resolution isn't available for this video.",
    "yt_cause_format_action": "Try \"Best\" or a lower resolution.",
    "yt_cause_live": "Live/upcoming video with no downloadable content yet.",
    "yt_cause_no_conn": "No connection to YouTube.",
    "yt_cause_engine": "The YouTube engine isn't installed.",
    "yt_cause_generic": "Could not complete: {e}",
    "dl_intro": "Paste YouTube video or playlist links and download the video (with a resolution "
                "choice) or audio only. You are responsible for respecting site terms and copyright.",
    "dl_resolution": "Resolution:",
    "dl_res_best": "Best",
    "dl_audio_only": "Audio only",
    "dl_audio_format": "Audio format:",
    "dl_container": "Video container:",
    "dl_start": "Start Download",
    "dl_log_frame": "Download Activity (real-time output)",
    "dl_need_output_dir": "Choose an output folder first.",
    "dl_need_ytdlp": "yt-dlp is required to download. Click the indicator above to install it.",
    "dl_ffmpeg_note": "FFmpeg is required to merge video+audio and to extract audio.",
    "dl_ffmpeg_nudge_q": "FFmpeg was not found. Without it, only progressive formats can be downloaded "
                         "(lower resolution, no audio extraction). Continue anyway?",
    "dl_links_label": "Paste video or playlist links (one per line):",
    "status_running_dl": "Downloading...",
    "dl_queue_frame": "Download Queue",
    "dl_options": "Download options",
    "btn_add": "+Add",
    "add_dialog_title": "Add YouTube links",
    "add_dialog_info": "Paste one or more YouTube links, one per line.\n"
                       "You can also paste a playlist link — the app will automatically "
                       "load the individual video links.",
})
TRANSLATIONS["en"].update({
    # v0.9.0
    "yt_queue_frame": "YouTube Transcription Queue",
    "save": "Save",
    "status_transcribing": "Transcribing...",
    "pause_every": "Pause every",
    "pause_videos_for": "videos for",
    "pause_minutes": "minutes",
    "pause_log_start": "Pausing {m} min after {n} videos (rate-limit protection)...\n",
    "pause_log_tick": "  ...resuming in ~{m} min\n",
    "pause_log_resume": "Resuming.\n",
    "dl_transcribe_after": "Transcribe video after download",
    "dl_define_whisper": "Define Whisper Settings",
    "dl_whisper_intro": "Choose the model, audio language, and vocabulary dictionary used to "
                        "transcribe the downloaded videos. Output formats (MD/SRT/TXT/JSON...) "
                        "follow Settings → Output formats.",
    "dl_need_whisper": "Whisper was not found. Open Settings → Whisper to locate or install it.",
    "dl_transcribe_needs_ffmpeg": "FFmpeg is required for transcription. Install FFmpeg and try again.",
    "dl_whisper_not_defined": "Before starting, click \"Define Whisper Settings\" and choose an "
                              "(installed) model, the audio language, and the dictionary.",
    "dl_transcribe_start": "Transcribing {name}...\n",
    "dl_transcribe_done": "Transcription complete.\n",
    "dl_transcribe_error": "[WARNING] Transcription failed: {e}\n",
    "dl_transcribe_no_file": "[WARNING] Could not locate the downloaded file to transcribe.\n",
    # grabber tab
    "tab_grabber": "YouTube Playlist Link Grabber",
    "grab_intro": "Paste one or more YouTube playlist OR channel/@handle links "
                  "(one per line). The app returns the individual video links.",
    "grab_input_label": "Playlists / channels (one per line)",
    "grab_btn": "Grab links",
    "grab_clear": "Clear",
    "grab_mode_title_link": "Title + link",
    "grab_mode_link_only": "Link only",
    "grab_output_label": "Videos found",
    "grab_copy": "Copy all",
    "grab_save": "Save to .txt",
    "grab_need_ytdlp": "yt-dlp is required for this tab. Open Settings → yt-dlp to install it.",
    "grab_no_input": "Paste at least one playlist or channel link.",
    "grab_working": "Grabbing links...",
    "grab_done_msg": "{n} video(s) found.",
    "grab_empty": "No videos found.",
    "grab_error": "Failed to grab links.",
    "grab_copied": "Copied to clipboard.",
    "grab_saved": "Saved to {path}",
    "grab_fetching": "Reading: {url}",
    "grab_channel_sub": "  sub-list: {name}",
    "dl_summary_transcribe_note": "+ transcription after each download",
})


# ==========================================================================
# Config / pure utilities (testable without GUI)
# ==========================================================================

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path, data):
    ensure_config_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_python_executable():
    """A Python interpreter usable for pip / -m markitdown. Avoids a frozen exe."""
    exe = sys.executable or ""
    if exe and os.path.basename(exe).lower().startswith("python"):
        return exe
    for name in ("python", "python3", "py"):
        w = shutil.which(name)
        if w:
            return w
    return exe or "python"


def find_whisper_path(saved_path=None):
    if saved_path and os.path.exists(saved_path):
        return saved_path
    for p in DEFAULT_WHISPER_PATHS:
        if os.path.exists(p):
            return p
    return shutil.which("whisper") or shutil.which("whisper.exe")


def whisper_is_available(saved_path=None):
    return bool(find_whisper_path(saved_path))


def find_ffmpeg(saved_path=None):
    if saved_path and os.path.exists(saved_path):
        return saved_path
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def markitdown_python(config_data):
    """Interpreter used to run markitdown (override or the app's python)."""
    override = (config_data or {}).get("markitdown_python") or ""
    if override and os.path.exists(override):
        return override
    return find_python_executable()


def markitdown_is_available(python_exe):
    """Fast probe: is the 'markitdown' module importable by python_exe?"""
    if not python_exe:
        return False
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             "import importlib.util,sys;"
             "sys.exit(0 if importlib.util.find_spec('markitdown') else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
            **subprocess_hidden_window_kwargs(),
        )
        return proc.returncode == 0
    except Exception:
        return False


def subprocess_hidden_window_kwargs():
    if os.name != "nt":
        return {"creationflags": 0, "startupinfo": None}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": 0, "startupinfo": startupinfo}


def subprocess_child_env():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def whisper_cache_dir():
    return os.path.join(str(Path.home()), ".cache", "whisper")


def model_file_name(cli_name):
    if cli_name == "turbo":
        return "large-v3-turbo.pt"
    return f"{cli_name}.pt"


def is_model_downloaded(cli_name, cache_dir=None):
    cache_dir = cache_dir or whisper_cache_dir()
    path = os.path.join(cache_dir, model_file_name(cli_name))
    return os.path.exists(path), path


def installed_model_clis(cache_dir=None):
    """Models actually present in the cache, in catalog order."""
    cache_dir = cache_dir or whisper_cache_dir()
    out = []
    for cli in ALL_MODEL_CLIS:
        if os.path.exists(os.path.join(cache_dir, model_file_name(cli))):
            out.append(cli)
    return out


def models_for_audio_language(audio_lang_code, only_installed=False, cache_dir=None):
    """Valid model CLIs; .en variants only when audio is English."""
    is_english = (audio_lang_code == "en")
    pool = installed_model_clis(cache_dir) if only_installed else ALL_MODEL_CLIS
    return [cli for cli in pool
            if not (MODEL_INFO[cli]["english_only"] and not is_english)]


def audio_lang_param(code):
    if code in AUDIO_LANG_OPTIONS:
        return AUDIO_LANG_OPTIONS[code]["param"]
    name = WHISPER_LANGUAGES.get(code)
    return name if name else None


def human_size(size_mb):
    return f"{size_mb} MB" if size_mb < 1000 else f"{size_mb / 1000:.1f} GB"


def fmt_hms(seconds):
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


_WHISPER_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?[.,]\d{1,3}\s*-->")


def parse_whisper_position_seconds(line):
    m = _WHISPER_TIME_RE.search(line)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is not None:
        return int(a) * 3600 + int(b) * 60 + int(c)
    return int(a) * 60 + int(b)


_FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")


def parse_ffmpeg_duration_seconds(text):
    m = _FFMPEG_DURATION_RE.search(text or "")
    if not m:
        return None
    h, mm, ss, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    total = int(h) * 3600 + int(mm) * 60 + int(ss)
    try:
        total += round(float("0." + frac))
    except ValueError:
        pass
    return total


def ffmpeg_probe_duration(ffmpeg_path, media_path, timeout=25):
    if not ffmpeg_path or not os.path.exists(media_path):
        return None
    try:
        proc = subprocess.run(
            [ffmpeg_path, "-i", media_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs(),
        )
        return parse_ffmpeg_duration_seconds(proc.stdout)
    except Exception:
        return None


def parse_replacements_text(raw):
    replacements = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        find, _, replace = line.partition("=")
        find = find.strip()
        replace = replace.strip()
        if not find:
            continue
        replacements.append([find, replace])
    return replacements


# --------------------------------------------------------------------------
# Subtitle -> clean prose (for AI-ready Markdown). MarkItDown passes SRT
# timestamps/indices through verbatim, which is useless for AI training, so we
# parse subtitles ourselves into timestamp-free paragraphs.
# --------------------------------------------------------------------------

def subtitle_to_prose(text, is_vtt=False, title=None):
    lines = (text or "").splitlines()
    cues = []
    cur = []

    def flush():
        if cur:
            t = " ".join(x.strip() for x in cur if x.strip())
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                cues.append(t)
            cur.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        if is_vtt and (line.upper().startswith("WEBVTT")
                       or line.startswith("NOTE") or line.startswith("STYLE")
                       or line.startswith("REGION")):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):  # srt cue index
            continue
        cur.append(line)
    flush()

    # Drop consecutive duplicate cues (Whisper sometimes repeats a line).
    deduped = []
    for c in cues:
        if not deduped or deduped[-1] != c:
            deduped.append(c)

    # Group cues into paragraphs at sentence boundaries.
    paragraphs, buf = [], []
    for c in deduped:
        buf.append(c)
        joined = " ".join(buf)
        if re.search(r"[.!?…][\"'”’)\]]?$", c) and len(joined) >= 200:
            paragraphs.append(joined)
            buf = []
    if buf:
        paragraphs.append(" ".join(buf))

    body = "\n\n".join(re.sub(r"[ \t]+", " ", p).strip()
                       for p in paragraphs if p.strip())
    if not body.strip():
        return ""
    header = f"# {title}\n\n" if title else ""
    return header + body.strip() + "\n"


def convert_subtitle_file_to_md(src_path, dst_path, title=None):
    is_vtt = src_path.lower().endswith(".vtt")
    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    prose = subtitle_to_prose(content, is_vtt=is_vtt, title=title)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(prose)
    return dst_path


def build_markitdown_command(python_exe, src_path, dst_path):
    return [python_exe, "-m", "markitdown", src_path, "-o", dst_path]


def build_pip_install_command(python_exe, package):
    return [python_exe, "-m", "pip", "install", "--upgrade", package]


# --------------------------------------------------------------------------
# YouTube transcript download (uses youtube-transcript-api, MarkItDown's engine)
# --------------------------------------------------------------------------

def youtube_video_id(url):
    """Extract the 11-char video id from common YouTube URL forms, or None."""
    if not url:
        return None
    url = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/")[0]
        return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [None])[0]
            return vid if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
        m = re.match(r"/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})", u.path)
        if m:
            return m.group(1)
    return None


def _secs_to_srt_ts(t):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_from_snippets(snippets):
    """snippets: list of {'text','start','duration'} -> SRT text."""
    out = []
    for i, sn in enumerate(snippets, 1):
        start = float(sn.get("start", 0.0))
        end = start + float(sn.get("duration", 0.0))
        text = (sn.get("text") or "").replace("\r", "").strip()
        out.append(f"{i}\n{_secs_to_srt_ts(start)} --> {_secs_to_srt_ts(end)}\n{text}\n")
    return "\n".join(out)


def fetch_youtube_transcript(video_id, preferred_code=None):
    """Return dict(snippets, language_code, is_generated, matched_pref, available).
    Raises youtube_transcript_api exceptions on failure (mapped by caller)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api import NoTranscriptFound
    api = YouTubeTranscriptApi()
    tlist = api.list(video_id)
    items = list(tlist)
    if not items:
        raise NoTranscriptFound(video_id, [preferred_code or "any"], tlist)

    def base_code(c):
        return (c or "").split("-")[0].lower()

    matched = []
    if preferred_code:
        matched = [t for t in items if base_code(t.language_code) == preferred_code.lower()]
    pool = matched if matched else items
    manual = [t for t in pool if not t.is_generated]
    chosen = manual[0] if manual else pool[0]
    fetched = chosen.fetch()
    raw = fetched.to_raw_data()
    available = sorted({t.language_code for t in items})
    return {
        "snippets": raw,
        "language_code": chosen.language_code,
        "is_generated": bool(chosen.is_generated),
        "matched_pref": bool(matched) or preferred_code is None,
        "available": available,
    }


def classify_ytdlp_error(text):
    """Map a yt-dlp / generic error string to a stable cause code."""
    t = (text or "").lower()
    if not t.strip():
        return "generic"
    if "members-only" in t or "members only" in t or "join this channel" in t:
        return "members_only"
    if "private video" in t or "this video is private" in t:
        return "private"
    if "confirm your age" in t or "age-restricted" in t or "age restricted" in t \
            or "inappropriate for some users" in t or "sign in to confirm your age" in t:
        return "age_restricted"
    if "not available in your country" in t or "not available in your region" in t \
            or "available in your country" in t or "available in your region" in t \
            or "blocked it in your country" in t or ("geo" in t and "block" in t):
        return "geo_blocked"
    if "not a bot" in t or "po token" in t or "potoken" in t \
            or "sign in to confirm you're not a bot" in t:
        return "bot_check"
    if "429" in t or "too many requests" in t or "requestblocked" in t \
            or "ipblocked" in t or "rate-limit" in t or "rate limit" in t \
            or "your ip" in t and "block" in t:
        return "rate_limited"
    if "requested format is not available" in t or "requested format" in t \
            or ("format" in t and "not available" in t):
        return "format_unavailable"
    if "live event will begin" in t or "premieres in" in t or "upcoming" in t \
            or "this live event" in t or "is live" in t and "no formats" in t:
        return "live_upcoming"
    if "no subtitles" in t or "no transcript" in t or "subtitles are disabled" in t \
            or "transcripts disabled" in t or "could not retrieve a transcript" in t:
        return "no_transcript"
    if "video unavailable" in t or "has been removed" in t or "no longer available" in t \
            or "does not exist" in t or "invalid" in t and "id" in t or "unavailable" in t:
        return "unavailable"
    if "urlopen error" in t or "getaddrinfo" in t or "failed to resolve" in t \
            or "name resolution" in t or "timed out" in t or "connection" in t \
            or "network" in t or "unreachable" in t:
        return "no_connection"
    return "generic"


def classify_youtube_error(exc_or_text):
    """Return a stable cause code for either a transcript-API exception or text."""
    def _s(e):
        try:
            return str(e)
        except Exception:
            return e.__class__.__name__
    if isinstance(exc_or_text, BaseException):
        exc = exc_or_text
        try:
            from youtube_transcript_api import (
                TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
                VideoUnplayable, AgeRestricted, RequestBlocked, IpBlocked,
                InvalidVideoId, YouTubeRequestFailed)
            if isinstance(exc, (RequestBlocked, IpBlocked)):
                return "rate_limited"
            if isinstance(exc, AgeRestricted):
                return "age_restricted"
            if isinstance(exc, (TranscriptsDisabled, NoTranscriptFound)):
                return "no_transcript"
            if isinstance(exc, (VideoUnavailable, InvalidVideoId)):
                code = classify_ytdlp_error(_s(exc))
                return code if code in ("members_only", "private", "geo_blocked",
                                        "age_restricted") else "unavailable"
            if isinstance(exc, VideoUnplayable):
                code = classify_ytdlp_error(_s(exc))
                return code if code != "generic" else "unavailable"
            if isinstance(exc, YouTubeRequestFailed):
                return "no_connection"
        except Exception:
            pass
        from urllib.error import URLError
        if isinstance(exc, (URLError, ConnectionError, TimeoutError)):
            return "no_connection"
        if isinstance(exc, ImportError):
            return "engine_missing"
        return classify_ytdlp_error(_s(exc))
    return classify_ytdlp_error(str(exc_or_text or ""))


# cause code -> (short message key, suggested action key)
YT_CAUSE_KEYS = {
    "no_transcript": "yt_cause_no_transcript",
    "members_only": "yt_cause_members",
    "private": "yt_cause_private",
    "unavailable": "yt_cause_unavailable",
    "age_restricted": "yt_cause_age",
    "geo_blocked": "yt_cause_geo",
    "rate_limited": "yt_cause_rate",
    "bot_check": "yt_cause_bot",
    "format_unavailable": "yt_cause_format",
    "live_upcoming": "yt_cause_live",
    "no_connection": "yt_cause_no_conn",
    "engine_missing": "yt_cause_engine",
    "generic": "yt_cause_generic",
}


def youtube_error_message(cause, strings, raw=""):
    """Return (short_message, suggested_action) localized for a cause code."""
    key = YT_CAUSE_KEYS.get(cause, "yt_cause_generic")
    if cause == "generic":
        short = strings.get("yt_cause_generic", "{e}")
        try:
            short = short.format(e=raw)
        except (KeyError, IndexError, ValueError):
            pass
    else:
        short = strings.get(key, key)
    action = strings.get(key + "_action", "")
    return short, action


def map_youtube_error(exc, strings):
    """Backward-compatible: localized short message for a transcript exception."""
    cause = classify_youtube_error(exc)
    try:
        raw = str(exc)
    except Exception:
        raw = exc.__class__.__name__
    short, _ = youtube_error_message(cause, strings, raw=raw)
    return short


# --------------------------------------------------------------------------
# yt-dlp helpers (playlist expansion + media download)
# --------------------------------------------------------------------------

def find_ytdlp(saved_path=None):
    if saved_path and os.path.exists(saved_path):
        return saved_path
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")


def ytdlp_is_available(python_exe=None):
    """Fast probe: is the 'yt_dlp' module importable? (CLI presence also counts)."""
    if find_ytdlp():
        return True
    python_exe = python_exe or find_python_executable()
    if not python_exe:
        return False
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             "import importlib.util,sys;"
             "sys.exit(0 if importlib.util.find_spec('yt_dlp') else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
            **subprocess_hidden_window_kwargs())
        return proc.returncode == 0
    except Exception:
        return False


def ytdlp_command_prefix(python_exe=None):
    """Prefer the yt-dlp executable; fall back to 'python -m yt_dlp'."""
    exe = find_ytdlp()
    if exe:
        return [exe]
    return [python_exe or find_python_executable(), "-m", "yt_dlp"]


def youtube_playlist_id(url):
    """Return the list id ONLY for a pure playlist URL (no v=), else None."""
    if not url:
        return None
    url = url.strip()
    if youtube_video_id(url):
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        return None
    if u.path != "/playlist":
        return None
    lst = parse_qs(u.query).get("list", [None])[0]
    if lst and re.fullmatch(r"[A-Za-z0-9_-]+", lst):
        return lst
    return None


def is_mix_playlist(list_id):
    """Endless auto/radio playlists (Mix) start with RD."""
    return bool(list_id) and str(list_id).upper().startswith("RD")


def build_ytdlp_flat_list_command(prefix, url):
    """Enumerate a playlist without downloading: flat JSON dump."""
    return list(prefix) + ["--flat-playlist", "-J", "--no-warnings", url]


def parse_flat_playlist_json(text):
    """Parse `yt-dlp --flat-playlist -J` output -> [{id,title,duration}]."""
    data = json.loads(text)
    entries = data.get("entries") if isinstance(data, dict) else None
    out = []
    for e in (entries or []):
        if not e:
            continue
        vid = e.get("id")
        if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(vid)):
            continue
        out.append({"id": vid, "title": e.get("title"),
                    "duration": e.get("duration")})
    return out


def build_ytdlp_download_command(prefix, url, out_dir, *, audio_only=False,
                                 audio_format="mp3", resolution="best",
                                 container="mp4", restrict_filenames=False,
                                 ffmpeg_location=None, single_video=True,
                                 progressive=False):
    """Build a yt-dlp download command (verified flags).

    progressive=True selects single-file formats that need no ffmpeg merge
    (used as a degraded fallback when ffmpeg is unavailable)."""
    cmd = list(prefix) + [
        "--newline", "--no-warnings",
        "--progress-template",
        "download:PROG|%(progress._percent_str)s|%(progress.eta)s",
    ]
    cmd.append("--no-playlist" if single_video else "--yes-playlist")
    if restrict_filenames:
        cmd.append("--restrict-filenames")
    if ffmpeg_location:
        cmd += ["--ffmpeg-location", ffmpeg_location]
    if audio_only:
        if progressive:
            cmd += ["-f", "bestaudio/best"]
        else:
            cmd += ["-f", "bestaudio/best", "-x",
                    "--audio-format", audio_format, "--audio-quality", "0"]
    else:
        if resolution in (None, "best", "Best", ""):
            h = None
        else:
            h = str(resolution)
        if progressive:
            fmt = "best" if h is None else f"best[height<={h}]/best"
            cmd += ["-f", fmt]
        else:
            if h is None:
                fmt = "bestvideo+bestaudio/best"
            else:
                fmt = (f"bestvideo[height<={h}]+bestaudio/"
                       f"best[height<={h}]/best")
            cmd += ["-f", fmt, "--merge-output-format", container]
    out_tmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
    cmd += ["-o", out_tmpl, url]
    return cmd


_YTDLP_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def parse_ytdlp_progress_line(line):
    """Extract a 0-100 percent from a yt-dlp progress line, or None."""
    if not line:
        return None
    m = _YTDLP_PCT_RE.search(line)
    if not m:
        return None
    try:
        return max(0.0, min(100.0, float(m.group(1))))
    except ValueError:
        return None


_RE_MERGE = re.compile(r'Merging formats into "(.+?)"')
_RE_EXTRACT = re.compile(r'\[ExtractAudio\] Destination: (.+)$')
_RE_DEST = re.compile(r'\[download\] Destination: (.+)$')
_RE_ALREADY = re.compile(r'\[download\] (.+) has already been downloaded')


def parse_ytdlp_final_path(text):
    """Best-effort path of the final downloaded/merged file from yt-dlp output."""
    if not text:
        return None
    merge = _RE_MERGE.findall(text)
    if merge:
        return merge[-1].strip()
    extract = _RE_EXTRACT.findall(text)
    if extract:
        return extract[-1].strip()
    already = _RE_ALREADY.findall(text)
    if already:
        return already[-1].strip()
    dest = _RE_DEST.findall(text)
    if dest:
        return dest[-1].strip()
    return None


# --------------------------------------------------------------------------
# Output filename helpers
# --------------------------------------------------------------------------

_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_FN_TRAILING = re.compile(r'[ .]+$')


def sanitize_filename(title, fallback="", max_len=150):
    """Make a title safe to use as a file name (no extension).

    Strips characters illegal on Windows/macOS/Linux, collapses whitespace,
    trims trailing dots/spaces, caps length, and falls back when empty."""
    if title is None:
        title = ""
    # collapse any whitespace (incl. tabs/newlines) to single spaces FIRST,
    # so they aren't deleted as control characters below
    name = re.sub(r"\s+", " ", str(title))
    name = _INVALID_FN_CHARS.sub("", name)
    name = name.strip()
    name = _FN_TRAILING.sub("", name)
    # avoid reserved Windows device names
    if name.upper() in {"CON", "PRN", "AUX", "NUL"} or \
            re.fullmatch(r"(?:COM|LPT)[1-9]", name.upper() or ""):
        name = "_" + name
    if len(name) > max_len:
        name = _FN_TRAILING.sub("", name[:max_len].strip())
    if not name:
        name = sanitize_filename(fallback, "", max_len) if fallback else ""
    return name or "untitled"


def unique_basename(base, used):
    """Return base, or base (2)/(3)/... if already in the `used` set (mutated)."""
    candidate = base
    n = 2
    lowered = {u.lower() for u in used}
    while candidate.lower() in lowered:
        candidate = f"{base} ({n})"
        n += 1
    used.add(candidate)
    return candidate


# Extensions checked for "transcript already exists" detection (item 10).
DUPLICATE_TRANSCRIPT_EXTENSIONS = ("md", "srt", "txt", "json")


def find_existing_transcripts(filepath):
    """Return the list of transcript extensions already present next to
    `filepath` (same folder, same filename stem), among
    DUPLICATE_TRANSCRIPT_EXTENSIONS."""
    folder = os.path.dirname(filepath)
    stem = os.path.splitext(os.path.basename(filepath))[0]
    found = []
    for ext in DUPLICATE_TRANSCRIPT_EXTENSIONS:
        candidate = os.path.join(folder, stem + "." + ext)
        if os.path.exists(candidate):
            found.append(ext)
    return found


def next_available_suffixed_stem(filepath):
    """base_2, base_3, ... — first stem for which NONE of the
    DUPLICATE_TRANSCRIPT_EXTENSIONS already exist in the same folder."""
    folder = os.path.dirname(filepath)
    stem = os.path.splitext(os.path.basename(filepath))[0]
    n = 2
    while True:
        candidate_stem = f"{stem}_{n}"
        if not any(os.path.exists(os.path.join(folder, candidate_stem + "." + ext))
                   for ext in DUPLICATE_TRANSCRIPT_EXTENSIONS):
            return candidate_stem
        n += 1


# --------------------------------------------------------------------------
# Duration / summary / speed-factor helpers
# --------------------------------------------------------------------------

def fmt_long_duration(seconds):
    """3h 34m 12s ; drops higher units when zero (34m 12s / 12s / 0s)."""
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def queue_length_summary(items):
    """(total, n_known, total_seconds) over items with a numeric .duration."""
    total = len(items)
    total_seconds = 0.0
    n_known = 0
    for it in items:
        d = getattr(it, "duration", None)
        if isinstance(d, (int, float)) and d and d > 0:
            total_seconds += float(d)
            n_known += 1
    return total, n_known, total_seconds


def estimate_time_seconds(total_seconds, speed_factor):
    if not total_seconds or total_seconds <= 0:
        return None
    return total_seconds * max(0.01, float(speed_factor or DEFAULT_SPEED_FACTOR))


def current_processing_index(done_count, total, running):
    """1-based index of the item CURRENTLY processing (not finished count)."""
    if total <= 0:
        return 0
    if not running:
        return min(done_count, total)
    return min(done_count + 1, total)


def compute_batch_percent(done_seconds, cur_pos, total_seconds,
                          done_items, total_items):
    """Audio-time percent when durations are known; else item-count percent."""
    if total_seconds and total_seconds > 0:
        val = (float(done_seconds) + max(0.0, float(cur_pos or 0))) / total_seconds * 100.0
        return max(0.0, min(100.0, val))
    if total_items and total_items > 0:
        return max(0.0, min(100.0, float(done_items) / total_items * 100.0))
    return 0.0


def update_speed_factor_rolling(entry, sample, cap=SPEED_FACTOR_SAMPLE_CAP):
    """Capped rolling average update of wall/audio realtime factor.

    `entry` is {"avg": float, "count": int} or None. The window is capped at
    `cap` samples so the average stays adaptive to model/hardware changes
    instead of being diluted forever by very old samples.
    """
    try:
        sample = float(sample)
    except (TypeError, ValueError):
        return entry
    if sample <= 0:
        return entry
    if not entry or not isinstance(entry, dict) or entry.get("avg", 0) <= 0:
        return {"avg": sample, "count": 1}
    old_avg = float(entry.get("avg", sample))
    old_count = int(entry.get("count", 1))
    n = min(old_count + 1, cap)
    new_avg = old_avg + (sample - old_avg) / n
    return {"avg": new_avg, "count": min(old_count + 1, cap)}


def load_eta_history():
    data = load_json(ETA_HISTORY_FILE, {})
    return data if isinstance(data, dict) else {}


def save_eta_history(history):
    ensure_config_dir()
    tmp_path = str(ETA_HISTORY_FILE) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, ETA_HISTORY_FILE)
    except OSError:
        pass


# --------------------------------------------------------------------------
# YouTube metadata + Markdown header (Feature E)
# --------------------------------------------------------------------------

def youtube_metadata(video_id, prefix=None, timeout=30):
    """Best-effort {video_id,title,duration,upload_date,url}. Network; mocked in tests."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    meta = {"video_id": video_id, "title": None, "duration": None,
            "upload_date": None, "url": url}
    pref = prefix if prefix is not None else (
        ytdlp_command_prefix() if ytdlp_is_available() else None)
    if pref:
        try:
            proc = subprocess.run(
                list(pref) + ["-J", "--no-warnings", "--skip-download", url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
                **subprocess_hidden_window_kwargs())
            if proc.returncode == 0 and (proc.stdout or "").strip():
                d = json.loads(proc.stdout)
                meta["title"] = d.get("title")
                meta["duration"] = d.get("duration")
                meta["upload_date"] = d.get("upload_date")
                if meta["title"]:
                    return meta
        except Exception:
            pass
    if not meta["title"]:
        try:
            from urllib.parse import quote
            oembed = ("https://www.youtube.com/oembed?format=json&url="
                      + quote(url, safe=""))
            with urllib.request.urlopen(oembed, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
                meta["title"] = d.get("title")
        except Exception:
            pass
    return meta


def build_youtube_md_header(meta, strings):
    """Localized labels, verbatim values. Always 4 lines; placeholders if unknown."""
    meta = meta or {}
    unknown = strings.get("yt_md_unknown", "Unknown")
    title = meta.get("title")
    title = title if (title is not None and str(title) != "") else unknown
    dur = meta.get("duration")
    dur_str = fmt_hms(dur) if isinstance(dur, (int, float)) and dur and dur > 0 else "—"
    ud = meta.get("upload_date")
    if ud and re.fullmatch(r"\d{8}", str(ud)):
        ud = str(ud)
        date_str = f"{ud[0:4]}-{ud[4:6]}-{ud[6:8]}"
    else:
        date_str = unknown
    url = meta.get("url") or (
        f"https://www.youtube.com/watch?v={meta.get('video_id', '')}")
    return "\n".join([
        f"{strings.get('yt_md_name', 'Video Name')}: {title}",
        f"{strings.get('yt_md_duration', 'Video Duration')}: {dur_str}",
        f"{strings.get('yt_md_date', 'Date')}: {date_str}",
        f"{strings.get('yt_md_link', 'Link')}: {url}",
    ])


def sleep_with_jitter(stop_flag, lo, hi):
    """Cancellable randomized delay in [lo, hi] seconds."""
    import random
    target = random.uniform(lo, hi)
    end = time.time() + target
    while time.time() < end:
        if stop_flag is not None and stop_flag.is_set():
            return
        time.sleep(0.05)


def cancellable_sleep(stop_flag, seconds, tick_cb=None):
    """Sleep `seconds`, checking stop_flag every 0.2s. tick_cb(remaining_int)
    is called about once per second. Returns False if interrupted."""
    end = time.time() + max(0.0, float(seconds))
    last_tick = None
    while time.time() < end:
        if stop_flag is not None and stop_flag.is_set():
            return False
        if tick_cb is not None:
            rem = int(round(end - time.time()))
            if rem != last_tick:
                last_tick = rem
                try:
                    tick_cb(rem)
                except Exception:
                    pass
        time.sleep(0.2)
    return not (stop_flag is not None and stop_flag.is_set())


def build_whisper_command(whisper_exe, media_path, out_dir, model, task,
                          lang_param, initial_prompt):
    """Pure: build the Whisper CLI command (output_format all)."""
    cmd = [whisper_exe, media_path, "--model", model, "--task", task,
           "--fp16", "False", "--output_dir", out_dir,
           "--output_format", "all", "--verbose", "True"]
    if lang_param:
        cmd += ["--language", lang_param]
    if initial_prompt:
        cmd += ["--initial_prompt", initial_prompt]
    return cmd


def apply_replacements_to_file(path, replacements):
    if not path or not os.path.exists(path) or not replacements:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for find, replace in replacements:
            if find:
                content = content.replace(find, replace)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        pass


def whisper_transcribe_file(whisper_exe, media_path, out_dir, *, model, task,
                            lang_param, initial_prompt, replacements,
                            keep_formats, stop_flag=None, log_cb=None):
    """Run Whisper once on a media file, write the kept formats (+ md derived
    from the subtitle), apply dictionary replacements, prune unwanted formats.
    Returns the output base name, or None if cancelled. Used by the
    'transcribe after download' option. Mirrors TranscriptionWorker logic."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(media_path))[0]
    cmd = build_whisper_command(whisper_exe, media_path, out_dir, model, task,
                                lang_param, initial_prompt)
    if log_cb:
        log_cb("Command: " + " ".join(cmd) + "\n")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
        env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
    for line in proc.stdout:
        if stop_flag is not None and stop_flag.is_set():
            try:
                proc.terminate()
            except OSError:
                pass
            break
        if log_cb:
            log_cb(line)
    proc.wait()
    if stop_flag is not None and stop_flag.is_set():
        return None
    if proc.returncode != 0:
        raise RuntimeError(f"whisper exited with code {proc.returncode}.")

    def fp(ext):
        return os.path.join(out_dir, base + "." + ext)

    if replacements:
        for ext in ("txt", "srt", "vtt", "tsv"):
            apply_replacements_to_file(fp(ext), replacements)
    if "md" in (keep_formats or []):
        made = False
        for ext in ("srt", "vtt"):
            if os.path.exists(fp(ext)):
                convert_subtitle_file_to_md(fp(ext), fp("md"), title=base)
                made = True
                break
        if not made and os.path.exists(fp("txt")):
            with open(fp("txt"), "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
            prose = "\n\n".join(s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip())
            with open(fp("md"), "w", encoding="utf-8") as f:
                f.write((f"# {base}\n\n" + prose).strip() + "\n")
        if replacements:
            apply_replacements_to_file(fp("md"), replacements)
    for ext in WHISPER_FORMATS:
        if ext not in (keep_formats or []) and os.path.exists(fp(ext)):
            try:
                os.remove(fp(ext))
            except OSError:
                pass
    return base


# --------------------------------------------------------------------------
# Time-range clipping + timestamp shifting on output
# --------------------------------------------------------------------------

_HMS_INPUT_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?\s*$")


def parse_hms_to_seconds(text):
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    m = _HMS_INPUT_RE.match(text)
    if not m:
        return None
    h, mm, ss, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    try:
        total = int(mm) * 60 + int(ss)
        if h:
            total = int(h) * 3600 + total
        if frac:
            total += float("0." + frac)
        return float(total)
    except ValueError:
        return None


def seconds_to_hms_input(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def build_ffmpeg_clip_command(ffmpeg_path, src_path, dst_path, start_seconds, end_seconds):
    duration = max(0.0, end_seconds - start_seconds)
    return [ffmpeg_path, "-y", "-ss", f"{start_seconds:.3f}", "-i", src_path,
            "-t", f"{duration:.3f}", "-c", "copy", dst_path]


def shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=False):
    sep = "." if is_vtt else ","
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")

    def _shift(m):
        h, mm, ss, ms = (int(m.group(1)), int(m.group(2)),
                         int(m.group(3)), int(m.group(4)))
        total_ms = ((h * 3600 + mm * 60 + ss) * 1000 + ms
                    + int(round(offset_seconds * 1000)))
        total_ms = max(0, total_ms)
        h2, rem = divmod(total_ms, 3600_000)
        m2, rem = divmod(rem, 60_000)
        s2, ms2 = divmod(rem, 1000)
        return f"{h2:02d}:{m2:02d}:{s2:02d}{sep}{ms2:03d}"

    return pattern.sub(_shift, content)


def shift_tsv_timestamps(content, offset_seconds):
    offset_ms = int(round(offset_seconds * 1000))
    lines = content.splitlines(keepends=False)
    if not lines:
        return content
    out = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            out.append(line)
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                parts[0] = str(int(parts[0]) + offset_ms)
                parts[1] = str(int(parts[1]) + offset_ms)
            except ValueError:
                pass
        out.append("\t".join(parts))
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def shift_json_timestamps(content, offset_seconds):
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content

    def _bump(obj):
        if isinstance(obj, dict):
            for key in ("start", "end"):
                if key in obj and isinstance(obj[key], (int, float)):
                    obj[key] = obj[key] + offset_seconds
            for v in obj.values():
                _bump(v)
        elif isinstance(obj, list):
            for v in obj:
                _bump(v)

    _bump(data)
    return json.dumps(data, ensure_ascii=False, indent=2)


def shift_output_timestamps(path, fmt, offset_seconds):
    if offset_seconds == 0 or fmt in ("txt", "md") or not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if fmt == "srt":
            content = shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=False)
        elif fmt == "vtt":
            content = shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=True)
        elif fmt == "tsv":
            content = shift_tsv_timestamps(content, offset_seconds)
        elif fmt == "json":
            content = shift_json_timestamps(content, offset_seconds)
        else:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        pass


# ==========================================================================
# Queue item + partial writer + workers
# ==========================================================================

class QueueItem:
    _next_id = 1

    def __init__(self, filepath):
        self.item_id = QueueItem._next_id
        QueueItem._next_id += 1
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.status = ST_PENDING
        self.error_message = ""
        self.output_dir = None
        self.output_txt = None
        self.output_srt = None
        self.output_md = None
        # v0.8.0: length/metadata (media or YouTube)
        self.duration = None        # seconds or None
        self.video_id = None
        self.title = None           # YouTube title (verbatim)
        self.upload_date = None     # YYYYMMDD or None
        self.meta_fetched = False
        self.size_bytes = None      # MD tab
        self.output_stem_override = None   # item 10: forced "_2"/"_3"... stem


class LiveQueue:
    """Thread-safe view over a list of QueueItem, shared between the GUI
    thread and a worker thread so the queue can be edited (add/remove/
    reorder pending items) while the worker is running (item 1).

    The worker pulls items one at a time via pop_next_pending(); it never
    iterates the underlying list directly, so GUI-side mutation is always
    safe. Items are identified by their stable `item_id`, never position.
    """

    def __init__(self, items):
        self._lock = threading.Lock()
        self._items = items   # SAME list object as the GUI's queue_items;
                               # all mutation (GUI and worker) must go through
                               # this class's locked methods to stay safe.

    def snapshot(self):
        with self._lock:
            return list(self._items)

    def pop_next_pending(self):
        """Returns the next ST_PENDING item (marking nothing), or None if
        none remain. Caller is responsible for setting status afterwards."""
        with self._lock:
            for it in self._items:
                if it.status == ST_PENDING:
                    return it
        return None

    def remaining_pending_count(self):
        with self._lock:
            return sum(1 for it in self._items if it.status == ST_PENDING)

    def add(self, item):
        with self._lock:
            self._items.append(item)

    def remove(self, item_id):
        """Removes by id only if currently ST_PENDING. Returns True if removed."""
        with self._lock:
            for i, it in enumerate(self._items):
                if it.item_id == item_id:
                    if it.status != ST_PENDING:
                        return False
                    del self._items[i]
                    return True
        return False

    def move(self, item_id, direction):
        """Swaps a pending item with its pending neighbor in `direction`
        (-1/+1). Returns True if moved."""
        with self._lock:
            idx = next((i for i, it in enumerate(self._items)
                       if it.item_id == item_id), None)
            if idx is None or self._items[idx].status != ST_PENDING:
                return False
            new = idx + direction
            if not (0 <= new < len(self._items)):
                return False
            if self._items[new].status != ST_PENDING:
                return False
            self._items[idx], self._items[new] = self._items[new], self._items[idx]
            return True

    def all_items(self):
        with self._lock:
            return list(self._items)


_WHISPER_SEGMENT_LINE_RE = re.compile(
    r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\s*-->\s*"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\]\s*(.*)$"
)


def parse_whisper_segment_line(line):
    m = _WHISPER_SEGMENT_LINE_RE.match(line.strip())
    if not m:
        return None
    sh, sm, ss, eh, em, es, text = m.groups()

    def _to_seconds(h, mm, ss):
        if ss is not None:
            return int(h) * 3600 + int(mm) * 60 + int(ss)
        return int(h) * 60 + int(mm)

    start = _to_seconds(sh, sm, ss)
    end = _to_seconds(eh, em, es)
    return start, end, text


class PartialTranscriptWriter:
    def __init__(self, path):
        self.path = path
        self._fh = None

    def open(self):
        try:
            self._fh = open(self.path, "w", encoding="utf-8")
        except OSError:
            self._fh = None

    def write_segment(self, text):
        if self._fh is None:
            return
        try:
            self._fh.write(text)
            if not text.endswith("\n"):
                self._fh.write("\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
        except (OSError, ValueError):
            pass

    def close(self):
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def discard(self):
        self.close()
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass


class ModelDownloadWorker(threading.Thread):
    """Force a Whisper model download by running it over 1s of silence."""

    def __init__(self, whisper_exe, model_name, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.whisper_exe = whisper_exe
        self.model_name = model_name
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _make_silent_wav(self, path, duration_seconds=1, sample_rate=16000):
        import wave
        import struct
        n_frames = duration_seconds * sample_rate
        with wave.open(path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(struct.pack("<h", 0) * n_frames)

    def run(self):
        tmp_dir = None
        try:
            import tempfile
            tmp_dir = tempfile.mkdtemp(prefix="whisper_model_check_")
            wav_path = os.path.join(tmp_dir, "silence.wav")
            self._make_silent_wav(wav_path)
            cmd = [self.whisper_exe, wav_path, "--model", self.model_name,
                   "--language", "English", "--fp16", "False",
                   "--output_dir", tmp_dir, "--output_format", "txt",
                   "--verbose", "True"]
            self.post("log", text="Command: " + " ".join(cmd) + "\n\n")
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)
            self.current_process.wait()
            if self.stop_flag.is_set():
                self.post("dl_finished", success=False, error="Canceled.")
                return
            if self.current_process.returncode != 0:
                self.post("dl_finished", success=False,
                          error=f"whisper exited with code {self.current_process.returncode}.")
                return
            downloaded, _ = is_model_downloaded(self.model_name)
            if downloaded:
                self.post("dl_model_ok")
                self.post("dl_finished", success=True)
            else:
                self.post("dl_finished", success=False,
                          error="Command finished but the model was not found in cache.")
        except Exception as e:
            self.post("dl_finished", success=False, error=str(e))
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir)
                except OSError:
                    pass

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class CommandStreamWorker(threading.Thread):
    """Generic: run a command, stream stdout to a queue, post a finish event."""

    def __init__(self, cmd, event_queue, stop_flag, tag="cmd", env=None):
        super().__init__(daemon=True)
        self.cmd = cmd
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.tag = tag
        self.env = env
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, "tag": self.tag, **kwargs})

    def run(self):
        try:
            self.current_process = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=self.env or subprocess_child_env(),
                **subprocess_hidden_window_kwargs())
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("cmd_log", text=line)
            self.current_process.wait()
            self.post("cmd_finished", returncode=self.current_process.returncode)
        except Exception as e:
            self.post("cmd_log", text=f"\n[ERROR] {e}\n")
            self.post("cmd_finished", returncode=-1)

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class YouTubeWorker(threading.Thread):
    """Download YouTube transcripts and save clean MD (always) + optional SRT/TXT."""

    def __init__(self, items, preferred_code, keep_srt, keep_txt, output_dir,
                 strings, event_queue, stop_flag, ytdlp_prefix=None,
                 delay_range=YT_TRANSCRIBE_DELAY, lang="en",
                 pause_every=0, pause_seconds=0):
        super().__init__(daemon=True)
        self.items = items
        self.preferred_code = preferred_code   # None = auto
        self.keep_srt = keep_srt
        self.keep_txt = keep_txt
        self.output_dir = output_dir
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.ytdlp_prefix = ytdlp_prefix
        self.delay_range = delay_range
        self.lang = lang
        self.pause_every = pause_every
        self.pause_seconds = pause_seconds

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _maybe_pause(self, processed, idx, total, log_kind):
        if (self.pause_every > 0 and self.pause_seconds > 0 and processed > 0
                and processed % self.pause_every == 0 and idx < total - 1
                and not self.stop_flag.is_set()):
            mins = max(1, int(round(self.pause_seconds / 60)))
            self.post(log_kind, text=self.s["pause_log_start"].format(
                n=self.pause_every, m=mins))

            def tick(rem):
                if rem > 0 and rem % 60 == 0:
                    self.post(log_kind, text=self.s["pause_log_tick"].format(
                        m=rem // 60))
            cancellable_sleep(self.stop_flag, self.pause_seconds, tick_cb=tick)
            if not self.stop_flag.is_set():
                self.post(log_kind, text=self.s["pause_log_resume"])

    def _fail(self, item, idx, vid, cause, raw=""):
        short, action = youtube_error_message(cause, self.s, raw=raw)
        item.status = ST_ERROR
        item.error_message = short
        self.post("yt_item_status", index=idx, status=ST_ERROR, error=short)
        self.post("yt_log", text=self.s["log_file_error"].format(name=vid, e=short))
        if action:
            self.post("yt_log", text="    " + action + "\n")
        return short, action

    def run(self):
        total = len(self.items)
        os.makedirs(self.output_dir, exist_ok=True)
        self._used_names = set()
        processed = 0
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("yt_item_status", index=idx, status=ST_SKIPPED)
                continue
            self.post("yt_item_status", index=idx, status=ST_RUNNING)
            self.post("yt_progress_index", index=idx)
            sep = "=" * 70
            self.post("yt_log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))
            vid = getattr(item, "video_id", None) or youtube_video_id(item.filepath)
            self.post("yt_log", text=self.s["yt_log_fetch"].format(vid=vid))

            cause = None
            res = None
            for attempt in range(2):   # one back-off retry on block
                try:
                    res = fetch_youtube_transcript(vid, self.preferred_code)
                    cause = None
                    break
                except Exception as e:
                    cause = classify_youtube_error(e)
                    try:
                        raw = str(e)
                    except Exception:
                        raw = e.__class__.__name__
                    if cause in BLOCK_CAUSES and attempt == 0:
                        self.post("yt_log", text=self.s["yt_log_backoff"])
                        sleep_with_jitter(self.stop_flag, BLOCK_BACKOFF_SECONDS,
                                          BLOCK_BACKOFF_SECONDS + 4)
                        if self.stop_flag.is_set():
                            break
                        continue
                    break

            if res is None:
                short, action = self._fail(item, idx, vid, cause or "generic", raw=raw)
                if cause in BLOCK_CAUSES:
                    self._stop_batch_block(idx, total)
                    return
            else:
                try:
                    self._write_outputs(item, vid, res)
                    item.status = ST_DONE
                    self.post("yt_item_status", index=idx, status=ST_DONE)
                    self.post("yt_log", text=self.s["log_file_done"].format(name=vid))
                except Exception as e:
                    item.status = ST_ERROR
                    item.error_message = str(e)
                    self.post("yt_item_status", index=idx, status=ST_ERROR, error=str(e))
                    self.post("yt_log", text=self.s["log_file_error"].format(name=vid, e=e))

            if idx < total - 1 and not self.stop_flag.is_set():
                sleep_with_jitter(self.stop_flag, *self.delay_range)
            processed += 1
            self._maybe_pause(processed, idx, total, "yt_log")
        self.post("yt_batch_finished")

    def _stop_batch_block(self, idx, total):
        for j in range(idx + 1, total):
            self.items[j].status = ST_PENDING
        self.post("yt_log", text=self.s["yt_log_batch_stopped"])
        self.post("yt_batch_blocked", message=self.s["yt_block_dialog"])
        self.post("yt_batch_finished")

    def _write_outputs(self, item, vid, res):
        out_dir = self.output_dir
        item.output_dir = out_dir
        srt_text = build_srt_from_snippets(res["snippets"])
        prose = subtitle_to_prose(srt_text, is_vtt=False, title=None)
        # Feature E: metadata header (best-effort)
        meta = None
        if getattr(item, "meta_fetched", False):
            meta = {"video_id": vid, "title": item.title,
                    "duration": item.duration, "upload_date": item.upload_date,
                    "url": f"https://www.youtube.com/watch?v={vid}"}
        else:
            try:
                meta = youtube_metadata(vid, prefix=self.ytdlp_prefix)
            except Exception:
                meta = {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}
        # duration fallback: last snippet end
        if not (isinstance(meta.get("duration"), (int, float)) and meta.get("duration")):
            snaps = res.get("snippets") or []
            if snaps:
                last = snaps[-1]
                meta["duration"] = float(last.get("start", 0.0)) + float(last.get("duration", 0.0))
        # Name outputs after the (original-language) video title; fall back to
        # the video id, and de-duplicate within this batch.
        if not getattr(self, "_used_names", None):
            self._used_names = set()
        base = unique_basename(
            sanitize_filename(meta.get("title"), fallback=vid), self._used_names)
        header = build_youtube_md_header(meta, self.s)
        md_path = os.path.join(out_dir, base + ".md")
        md_content = (header + "\n\n" + (prose or "")).rstrip() + "\n"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        item.output_md = md_path
        saved = [base + ".md"]
        if self.keep_srt:
            with open(os.path.join(out_dir, base + ".srt"), "w", encoding="utf-8") as f:
                f.write(srt_text)
            saved.append(base + ".srt")
        if self.keep_txt:
            with open(os.path.join(out_dir, base + ".txt"), "w", encoding="utf-8") as f:
                f.write(prose if prose else "")
            saved.append(base + ".txt")
        gen = self.s["yt_generated_suffix"] if res["is_generated"] else ""
        self.post("yt_log", text=self.s["yt_log_lang_used"].format(
            lang=res["language_code"], gen=gen))
        if self.preferred_code and not res["matched_pref"]:
            self.post("yt_log", text=self.s["yt_log_lang_mismatch"].format(
                want=self.preferred_code, got=res["language_code"],
                avail=", ".join(res["available"])))
        self.post("yt_log", text=self.s["yt_log_wrote"].format(files=", ".join(saved)))


class PlaylistExpandWorker(threading.Thread):
    """Enumerate a playlist (flat extraction) and post its video entries."""

    def __init__(self, prefix, url, strings, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.prefix = prefix
        self.url = url
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        cmd = build_ytdlp_flat_list_command(self.prefix, self.url)
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=120,
                **subprocess_hidden_window_kwargs())
        except Exception as e:
            self.post("expand_error", cause=classify_ytdlp_error(str(e)), raw=str(e))
            return
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            raw = (proc.stderr or proc.stdout or "")
            self.post("expand_error", cause=classify_ytdlp_error(raw), raw=raw.strip())
            return
        try:
            entries = parse_flat_playlist_json(proc.stdout)
        except Exception as e:
            self.post("expand_error", cause="generic", raw=str(e))
            return
        self.post("expand_done", entries=entries)


class LinkGrabWorker(threading.Thread):
    """Resolve one or more playlist/channel/@handle URLs into individual video
    links. Channel URLs may return nested tab-playlists, so we recurse once."""

    def __init__(self, urls, prefix, strings, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.urls = urls
        self.prefix = prefix
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _flat_list(self, url):
        cmd = build_ytdlp_flat_list_command(self.prefix, url)
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=180,
            **subprocess_hidden_window_kwargs())
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            raw = (proc.stderr or proc.stdout or "")
            raise RuntimeError(raw.strip() or "yt-dlp returned no data")
        return json.loads(proc.stdout)

    def _collect(self, url, depth, out):
        if self.stop_flag.is_set():
            return
        try:
            data = self._flat_list(url)
        except Exception as e:
            self.post("grab_log", text=self.s["yt_expand_error"].format(e=str(e)[:200]) + "\n")
            return
        entries = data.get("entries") if isinstance(data, dict) else None
        for e in (entries or []):
            if not e or self.stop_flag.is_set():
                continue
            vid = e.get("id")
            if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(vid)):
                out.append({"id": vid, "title": e.get("title"),
                            "url": f"https://www.youtube.com/watch?v={vid}"})
            elif depth < 1:
                nurl = e.get("url") or e.get("webpage_url")
                if nurl:
                    self.post("grab_log", text=self.s["grab_channel_sub"].format(
                        name=e.get("title") or nurl) + "\n")
                    self._collect(nurl, depth + 1, out)

    def run(self):
        out = []
        for url in self.urls:
            if self.stop_flag.is_set():
                break
            self.post("grab_log", text=self.s["grab_fetching"].format(url=url) + "\n")
            self._collect(url, 0, out)
        seen = set()
        uniq = []
        for e in out:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            uniq.append(e)
        self.post("grab_done", entries=uniq)


class DownloadWorker(threading.Thread):
    """Download media via yt-dlp (subprocess), with rate-limit protection."""

    def __init__(self, items, prefix, out_dir, *, audio_only, audio_format,
                 resolution, container, ffmpeg_location, strings, event_queue,
                 stop_flag, delay_range=YT_DOWNLOAD_DELAY, progressive=False,
                 pause_every=0, pause_seconds=0, transcribe=False,
                 whisper_exe=None, whisper_model="", whisper_lang_param=None,
                 whisper_task="transcribe", whisper_prompt="",
                 whisper_replacements=None, whisper_formats=None):
        super().__init__(daemon=True)
        self.live_queue = items   # LiveQueue instance (item 1: live editing)
        self.prefix = prefix
        self.out_dir = out_dir
        self.audio_only = audio_only
        self.audio_format = audio_format
        self.resolution = resolution
        self.container = container
        self.ffmpeg_location = ffmpeg_location
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.delay_range = delay_range
        self.progressive = progressive
        self.pause_every = pause_every
        self.pause_seconds = pause_seconds
        self.transcribe = transcribe
        self.whisper_exe = whisper_exe
        self.whisper_model = whisper_model
        self.whisper_lang_param = whisper_lang_param
        self.whisper_task = whisper_task
        self.whisper_prompt = whisper_prompt
        self.whisper_replacements = whisper_replacements or []
        self.whisper_formats = whisper_formats or []
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _maybe_pause(self, processed):
        if (self.pause_every > 0 and self.pause_seconds > 0 and processed > 0
                and processed % self.pause_every == 0
                and self.live_queue.remaining_pending_count() > 0
                and not self.stop_flag.is_set()):
            mins = max(1, int(round(self.pause_seconds / 60)))
            self.post("dl_log", text=self.s["pause_log_start"].format(
                n=self.pause_every, m=mins))

            def tick(rem):
                if rem > 0 and rem % 60 == 0:
                    self.post("dl_log", text=self.s["pause_log_tick"].format(m=rem // 60))
            cancellable_sleep(self.stop_flag, self.pause_seconds, tick_cb=tick)
            if not self.stop_flag.is_set():
                self.post("dl_log", text=self.s["pause_log_resume"])

    def _capture_downloaded_path(self, since):
        """Newest media file in out_dir modified at/after `since`."""
        best = None
        best_m = since - 1
        try:
            for fn in os.listdir(self.out_dir):
                p = os.path.join(self.out_dir, fn)
                if (os.path.isfile(p)
                        and os.path.splitext(fn)[1].lower() in MEDIA_EXTENSIONS):
                    m = os.path.getmtime(p)
                    if m >= best_m:
                        best_m = m
                        best = p
        except OSError:
            pass
        return best

    def _transcribe_after(self, item, since):
        if not (self.transcribe and self.whisper_exe):
            return
        path = self._capture_downloaded_path(since)
        if not path:
            self.post("dl_log", text=self.s["dl_transcribe_no_file"])
            return
        self.post("dl_log", text=self.s["dl_transcribe_start"].format(
            name=os.path.basename(path)))
        self.post("dl_substatus", item_id=item.item_id, text=self.s["status_transcribing"])
        try:
            whisper_transcribe_file(
                self.whisper_exe, path, self.out_dir,
                model=self.whisper_model, task=self.whisper_task,
                lang_param=self.whisper_lang_param,
                initial_prompt=self.whisper_prompt,
                replacements=self.whisper_replacements,
                keep_formats=self.whisper_formats,
                stop_flag=self.stop_flag,
                log_cb=lambda t: self.post("dl_log", text=t))
            if not self.stop_flag.is_set():
                self.post("dl_log", text=self.s["dl_transcribe_done"])
        except Exception as e:
            self.post("dl_log", text=self.s["dl_transcribe_error"].format(e=e))

    def _run_once(self, item, vid):
        """Run yt-dlp for one item; return (returncode, captured_text)."""
        url = f"https://www.youtube.com/watch?v={vid}"
        cmd = build_ytdlp_download_command(
            self.prefix, url, self.out_dir, audio_only=self.audio_only,
            audio_format=self.audio_format, resolution=self.resolution,
            container=self.container, ffmpeg_location=self.ffmpeg_location,
            single_video=True, progressive=self.progressive)
        captured = []
        self.current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                try:
                    self.current_process.terminate()
                except OSError:
                    pass
                break
            captured.append(line)
            pct = parse_ytdlp_progress_line(line)
            if pct is not None:
                self.post("dl_progress", percent=pct)
            else:
                self.post("dl_log", text=line)
        self.current_process.wait()
        return self.current_process.returncode, "".join(captured[-40:])

    def run(self):
        os.makedirs(self.out_dir, exist_ok=True)
        processed = 0
        while True:
            if self.stop_flag.is_set():
                break
            item = self.live_queue.pop_next_pending()
            if item is None:
                break
            vid = getattr(item, "video_id", None) or youtube_video_id(item.filepath)
            self.post("dl_item_status", item_id=item.item_id, status=ST_RUNNING)
            self.post("dl_progress_item", item_id=item.item_id)
            processed += 1
            total_hint = processed + self.live_queue.remaining_pending_count()
            sep = "=" * 70
            self.post("dl_log", text=self.s["log_file_start"].format(
                sep=sep, i=processed, n=total_hint, name=item.filename))

            cause = None
            rc = -1
            since = time.time() - 1
            for attempt in range(2):
                try:
                    rc, tail = self._run_once(item, vid)
                except Exception as e:
                    rc, tail = -1, str(e)
                if rc == 0:
                    cause = None
                    break
                cause = classify_ytdlp_error(tail)
                if cause in BLOCK_CAUSES and attempt == 0 and not self.stop_flag.is_set():
                    self.post("dl_log", text=self.s["yt_log_backoff"])
                    sleep_with_jitter(self.stop_flag, BLOCK_BACKOFF_SECONDS,
                                      BLOCK_BACKOFF_SECONDS + 6)
                    if self.stop_flag.is_set():
                        break
                    continue
                break

            if self.stop_flag.is_set() and rc != 0:
                item.status = ST_SKIPPED
                self.post("dl_item_status", item_id=item.item_id, status=ST_SKIPPED)
                break
            if rc == 0:
                item.output_dir = self.out_dir
                self._transcribe_after(item, since)
                item.status = ST_DONE
                self.post("dl_item_status", item_id=item.item_id, status=ST_DONE)
                self.post("dl_log", text=self.s["log_file_done"].format(name=vid))
            else:
                short, action = youtube_error_message(cause or "generic", self.s, raw=tail)
                item.status = ST_ERROR
                item.error_message = short
                self.post("dl_item_status", item_id=item.item_id, status=ST_ERROR, error=short)
                self.post("dl_log", text=self.s["log_file_error"].format(name=vid, e=short))
                if action:
                    self.post("dl_log", text="    " + action + "\n")
                if cause in BLOCK_CAUSES:
                    # Remaining items are still ST_PENDING (never popped), so
                    # they're left untouched for a future run, same as before.
                    self.post("dl_log", text=self.s["yt_log_batch_stopped"])
                    self.post("dl_batch_blocked", message=self.s["yt_block_dialog"])
                    self.post("dl_batch_finished")
                    return
            if self.live_queue.remaining_pending_count() > 0 and not self.stop_flag.is_set():
                sleep_with_jitter(self.stop_flag, *self.delay_range)
            self._maybe_pause(processed)
        # Any items still ST_PENDING here means stop was requested mid-batch.
        if self.stop_flag.is_set():
            for it in self.live_queue.all_items():
                if it.status == ST_PENDING:
                    it.status = ST_SKIPPED
                    self.post("dl_item_status", item_id=it.item_id, status=ST_SKIPPED)
        self.post("dl_batch_finished")

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class TranscriptionWorker(threading.Thread):
    def __init__(self, live_queue, whisper_exe, ffmpeg_path, lang_param, task,
                 model_name, initial_prompt, replacements, keep_formats,
                 output_dir_mode, fixed_output_dir, clip_range, strings,
                 event_queue, stop_flag):
        super().__init__(daemon=True)
        self.live_queue = live_queue
        self.whisper_exe = whisper_exe
        self.ffmpeg_path = ffmpeg_path
        self.lang_param = lang_param
        self.task = task
        self.model_name = model_name
        self.initial_prompt = initial_prompt
        self.replacements = replacements
        self.keep_formats = keep_formats
        self.output_dir_mode = output_dir_mode
        self.fixed_output_dir = fixed_output_dir
        self.clip_range = clip_range
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        processed = 0
        while True:
            if self.stop_flag.is_set():
                break
            item = self.live_queue.pop_next_pending()
            if item is None:
                break
            processed += 1
            total_hint = processed + self.live_queue.remaining_pending_count()
            self.post("item_status", item_id=item.item_id, status=ST_RUNNING)
            sep = "=" * 70
            self.post("log", text=self.s["log_file_start"].format(
                sep=sep, i=processed, n=total_hint, name=item.filename))
            self.post("log", text=self.s["log_probing"])
            full_duration = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
            if full_duration:
                self.post("log", text=self.s["log_duration_ok"].format(dur=fmt_hms(full_duration)))
            else:
                self.post("log", text=self.s["log_duration_fail"])
            offset_seconds = 0.0
            effective_duration = full_duration
            if self.clip_range:
                start_s, end_s = self.clip_range
                if full_duration:
                    end_s = min(end_s, full_duration)
                offset_seconds = start_s
                effective_duration = max(0.0, end_s - start_s)
            self.post("duration", item_id=item.item_id, seconds=effective_duration)
            try:
                self._transcribe_one(item, item.item_id, offset_seconds)
                if self.stop_flag.is_set():
                    item.status = ST_SKIPPED
                    self.post("item_status", item_id=item.item_id, status=ST_SKIPPED)
                else:
                    item.status = ST_DONE
                    self.post("item_status", item_id=item.item_id, status=ST_DONE)
                    self.post("log", text=self.s["log_file_done"].format(name=item.filename))
            except Exception as e:
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("item_status", item_id=item.item_id, status=ST_ERROR, error=str(e))
                self.post("log", text=self.s["log_file_error"].format(name=item.filename, e=e))
        # Any items still ST_PENDING here means stop was requested mid-batch.
        if self.stop_flag.is_set():
            for it in self.live_queue.all_items():
                if it.status == ST_PENDING:
                    it.status = ST_SKIPPED
                    self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
        self.post("batch_finished")

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def _prepare_clip_if_needed(self, item, idx, tmp_dir):
        if not self.clip_range:
            return item.filepath
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            raise RuntimeError("Time-range clipping requested, but ffmpeg was not found.")
        start_s, end_s = self.clip_range
        ext = os.path.splitext(item.filepath)[1] or ".mkv"
        clip_path = os.path.join(tmp_dir, f"clip_{idx}{ext}")
        cmd = build_ffmpeg_clip_command(self.ffmpeg_path, item.filepath, clip_path, start_s, end_s)
        self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", env=subprocess_child_env(),
            **subprocess_hidden_window_kwargs())
        if proc.returncode != 0 or not os.path.exists(clip_path):
            raise RuntimeError(f"ffmpeg clip failed (code {proc.returncode}).\n{proc.stdout}")
        return clip_path

    def _transcribe_one(self, item, idx, offset_seconds):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)
        item.output_dir = out_dir
        base = item.output_stem_override or os.path.splitext(os.path.basename(item.filepath))[0]
        partial = PartialTranscriptWriter(os.path.join(out_dir, base + ".partial.txt"))
        partial.open()
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="whisper_clip_")
        try:
            input_path = self._prepare_clip_if_needed(item, idx, tmp_dir)
            cmd = [self.whisper_exe, input_path, "--model", self.model_name,
                   "--task", self.task, "--fp16", "False",
                   "--output_dir", out_dir, "--output_format", "all",
                   "--verbose", "True"]
            if self.lang_param:
                cmd.extend(["--language", self.lang_param])
            if self.initial_prompt:
                cmd.extend(["--initial_prompt", self.initial_prompt])
            self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
            self.post("phase", item_id=item.item_id, phase="preparing")
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
            saw_first_segment = False
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)
                seg = parse_whisper_segment_line(line)
                if seg is not None:
                    if not saw_first_segment:
                        saw_first_segment = True
                        self.post("phase", item_id=item.item_id, phase="transcribing")
                    seg_start, seg_end, seg_text = seg
                    partial.write_segment(seg_text.strip())
                    self.post("progress_tick", item_id=item.item_id, seconds=seg_start)
            self.current_process.wait()
            if not self.stop_flag.is_set() and self.current_process.returncode != 0:
                raise RuntimeError(
                    f"whisper exited with code {self.current_process.returncode}.")
            if self.stop_flag.is_set():
                return

            def fpath(ext):
                return os.path.join(out_dir, base + "." + ext)

            # Whisper names its own outputs after input_path's stem (which is
            # the clip temp file when clipping, or the original media file
            # otherwise). Rename to `base` whenever it differs — this covers
            # both the clip-temp-file case and the item 10 duplicate-avoidance
            # override case (whisper has no knowledge of our renamed stem).
            actual_whisper_base = os.path.splitext(os.path.basename(input_path))[0]
            if actual_whisper_base != base:
                for ext in WHISPER_FORMATS:
                    src = os.path.join(out_dir, actual_whisper_base + "." + ext)
                    if os.path.exists(src):
                        dst = fpath(ext)
                        try:
                            if os.path.exists(dst):
                                os.remove(dst)
                            os.replace(src, dst)
                        except OSError:
                            pass

            # Shift timestamps back to the original timeline (clip case).
            if self.clip_range and offset_seconds:
                for ext in WHISPER_FORMATS:
                    shift_output_timestamps(fpath(ext), ext, offset_seconds)

            # Apply dictionary replacements to whisper text formats first, so
            # the MD (derived from SRT) inherits the corrections.
            if self.replacements:
                for ext in ("txt", "srt", "vtt", "tsv"):
                    self._apply_replacements(fpath(ext))

            # Build clean MD from the subtitle (prefer SRT, then VTT, then TXT).
            if "md" in self.keep_formats:
                self.post("log", text=self.s["log_md_make"])
                made = False
                for ext in ("srt", "vtt"):
                    p = fpath(ext)
                    if os.path.exists(p):
                        convert_subtitle_file_to_md(p, fpath("md"), title=base)
                        made = True
                        break
                if not made and os.path.exists(fpath("txt")):
                    with open(fpath("txt"), "r", encoding="utf-8", errors="replace") as f:
                        txt = f.read()
                    prose = "\n\n".join(s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip())
                    with open(fpath("md"), "w", encoding="utf-8") as f:
                        f.write((f"# {base}\n\n" + prose).strip() + "\n")
                if self.replacements:
                    self._apply_replacements(fpath("md"))

            # Remove whisper formats the user did not keep.
            for ext in WHISPER_FORMATS:
                if ext not in self.keep_formats:
                    p = fpath(ext)
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

            item.output_txt = fpath("txt") if os.path.exists(fpath("txt")) else None
            item.output_srt = fpath("srt") if os.path.exists(fpath("srt")) else None
            item.output_md = fpath("md") if os.path.exists(fpath("md")) else None
            partial.discard()
        finally:
            partial.close()
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except OSError:
                pass

    def _apply_replacements(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for find, replace in self.replacements:
                if not find:
                    continue
                content = content.replace(find, replace)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            self.post("log", text=self.s["log_dict_warn"].format(path=path, e=e))

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class ConversionWorker(threading.Thread):
    """MD File Generation tab: convert docs/subtitles to clean Markdown."""

    def __init__(self, items, python_exe, markitdown_ok, output_dir_mode,
                 fixed_output_dir, strings, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.items = items
        self.python_exe = python_exe
        self.markitdown_ok = markitdown_ok
        self.output_dir_mode = output_dir_mode
        self.fixed_output_dir = fixed_output_dir
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def run(self):
        total = len(self.items)
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("md_item_status", index=idx, status=ST_SKIPPED)
                continue
            self.post("md_item_status", index=idx, status=ST_RUNNING)
            sep = "=" * 70
            self.post("md_log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))
            try:
                self._convert_one(item)
                if self.stop_flag.is_set():
                    item.status = ST_SKIPPED
                    self.post("md_item_status", index=idx, status=ST_SKIPPED)
                else:
                    item.status = ST_DONE
                    self.post("md_item_status", index=idx, status=ST_DONE)
                    self.post("md_log", text=self.s["log_file_done"].format(name=item.filename))
            except Exception as e:
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("md_item_status", index=idx, status=ST_ERROR, error=str(e))
                self.post("md_log", text=self.s["log_file_error"].format(name=item.filename, e=e))
        self.post("md_batch_finished")

    def _convert_one(self, item):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)
        item.output_dir = out_dir
        base = os.path.splitext(os.path.basename(item.filepath))[0]
        dst = os.path.join(out_dir, base + ".md")
        ext = os.path.splitext(item.filepath)[1].lower()
        if ext in SUBTITLE_EXTENSIONS:
            self.post("md_log", text=self.s["log_md_make"])
            convert_subtitle_file_to_md(item.filepath, dst, title=base)
            item.output_md = dst
            return
        if not self.markitdown_ok:
            raise RuntimeError("MarkItDown is required to convert this file type.")
        cmd = build_markitdown_command(self.python_exe, item.filepath, dst)
        self.post("md_log", text=self.s["log_md_markitdown"].format(name=item.filename))
        self.post("md_log", text="Command: " + " ".join(cmd) + "\n")
        self.current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                self.current_process.terminate()
                break
            self.post("md_log", text=line)
        self.current_process.wait()
        if not self.stop_flag.is_set() and self.current_process.returncode != 0:
            raise RuntimeError(f"markitdown exited with code {self.current_process.returncode}.")
        item.output_md = dst if os.path.exists(dst) else None

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


# ==========================================================================
# ffmpeg archive extraction (testable helper)
# ==========================================================================

def extract_ffmpeg_archive(archive_path, dest_dir):
    """Extract a downloaded ffmpeg archive and return the path to the ffmpeg
    executable copied into dest_dir, or None if not found."""
    archive_path = str(archive_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    extract_root = dest_dir / "_extract"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(extract_root)
    elif archive_path.lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".txz")):
        with tarfile.open(archive_path) as tf:
            tf.extractall(extract_root)
    else:
        return None

    candidates = []
    for root, _dirs, files in os.walk(extract_root):
        for name in files:
            low = name.lower()
            if low == "ffmpeg.exe" or low == "ffmpeg":
                candidates.append(os.path.join(root, name))
    if not candidates:
        return None
    src = candidates[0]
    final_name = "ffmpeg.exe" if src.lower().endswith(".exe") else "ffmpeg"
    final_path = dest_dir / final_name
    shutil.copy2(src, final_path)
    if not final_name.endswith(".exe"):
        try:
            os.chmod(final_path, 0o755)
        except OSError:
            pass
    shutil.rmtree(extract_root, ignore_errors=True)
    return str(final_path)


# ==========================================================================
# Scrollable frame (fixes the "text hidden when window shrinks" bug)
# ==========================================================================

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical",
                                     command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class TwoToneProgress(tk.Frame):
    """Determinate progress bar: green fill on a light track with a centered
    NN% label rendered two-tone — white over the filled portion, dark over the
    unfilled portion (no opaque box). Implemented with a clipping frame so the
    text colour splits exactly at the fill edge."""
    TRACK = "#e3e6ea"
    FILL = "#1a7f37"
    DARK = "#222222"
    LIGHT = "#ffffff"

    def __init__(self, master, height=22, **kw):
        super().__init__(master, height=height, bg=self.TRACK,
                         highlightthickness=1, highlightbackground="#c2c7ce", **kw)
        self._pct = 0.0
        self._text = ""
        self.grid_propagate(False)
        self.pack_propagate(False)
        font = ("TkDefaultFont", 9, "bold")
        # bottom layer: full-width track, dark centered text
        self._base = tk.Label(self, bg=self.TRACK, fg=self.DARK, text="",
                              font=font, anchor="center")
        self._base.place(x=0, y=0, relwidth=1, relheight=1)
        # top layer: green clipping frame (width = pct) holding a full-width
        # white centered label, so only the filled part of the white text shows
        self._clip = tk.Frame(self, bg=self.FILL)
        self._clip.place(x=0, y=0, relheight=1, relwidth=0)
        self._fill_label = tk.Label(self._clip, bg=self.FILL, fg=self.LIGHT,
                                    text="", font=font, anchor="center")
        self.bind("<Configure>", lambda e: self._relayout())

    def set_percent(self, pct, text=None):
        try:
            self._pct = max(0.0, min(100.0, float(pct)))
        except (TypeError, ValueError):
            self._pct = 0.0
        if text is not None:
            self._text = text
        self._base.config(text=self._text)
        self._fill_label.config(text=self._text)
        self._relayout()

    def set_text(self, text):
        self.set_percent(self._pct, text=text or "")

    # accept ttk-style configure(value=...) as a fallback
    def configure(self, **kw):
        if "value" in kw:
            self.set_percent(kw.pop("value"))
        if kw:
            super().configure(**kw)
    config = configure

    def _relayout(self):
        self.update_idletasks()
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        self._clip.place_configure(relwidth=self._pct / 100.0)
        # full-bar-width label inside the (narrower) clip keeps text centered
        # on the BAR, so it lines up with the dark base text underneath
        self._fill_label.place(x=0, y=0, width=w, height=h)


def make_scrollable_queue(parent, columns, height=12):
    """Treeview + wired vertical scrollbar; wheel routed to the tree (returns
    'break' so an enclosing ScrollableFrame doesn't also scroll). Returns
    (wrapper_frame, tree, scrollbar)."""
    wrap = ttk.Frame(parent)
    wrap.columnconfigure(0, weight=1)
    wrap.rowconfigure(0, weight=1)
    tree = ttk.Treeview(wrap, columns=columns, show="headings",
                        height=height, selectmode="extended")
    vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")

    def _wheel(event):
        if event.num == 4:
            tree.yview_scroll(-1, "units")
        elif event.num == 5:
            tree.yview_scroll(1, "units")
        else:
            tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    tree.bind("<MouseWheel>", _wheel)
    tree.bind("<Button-4>", _wheel)
    tree.bind("<Button-5>", _wheel)
    _enable_explorer_multiselect(tree)
    return wrap, tree, vsb


def _enable_explorer_multiselect(tree):
    """Windows-Explorer-style selection: Shift+Up/Down extend the selection
    from an anchor; Ctrl+A selects all. (Mouse shift/ctrl-click already work
    via selectmode='extended'.)"""
    tree._sel_anchor = None

    def _extend(forward):
        items = tree.get_children()
        if not items:
            return "break"
        cur = tree.focus()
        if not cur:
            sel = tree.selection()
            cur = sel[-1] if sel else items[0]
        if tree._sel_anchor not in items:
            tree._sel_anchor = cur
        try:
            ci = items.index(cur)
        except ValueError:
            ci = 0
        ni = max(0, min(len(items) - 1, ci + (1 if forward else -1)))
        new = items[ni]
        tree.focus(new)
        tree.see(new)
        ai = items.index(tree._sel_anchor)
        lo, hi = sorted((ai, ni))
        tree.selection_set(items[lo:hi + 1])
        return "break"

    def _select_all(_e=None):
        kids = tree.get_children()
        if kids:
            tree.selection_set(kids)
            tree._sel_anchor = kids[0]
        return "break"

    def _reset_anchor_click(e):
        row = tree.identify_row(e.y)
        if row:
            tree._sel_anchor = row

    def _reset_anchor_arrow(_e):
        tree.after(1, lambda: setattr(tree, "_sel_anchor", tree.focus()))

    tree.bind("<Shift-Down>", lambda e: _extend(True))
    tree.bind("<Shift-Up>", lambda e: _extend(False))
    tree.bind("<Control-a>", _select_all)
    tree.bind("<Control-A>", _select_all)
    tree.bind("<Button-1>", _reset_anchor_click, add="+")
    tree.bind("<Down>", _reset_anchor_arrow, add="+")
    tree.bind("<Up>", _reset_anchor_arrow, add="+")
    # exposed for programmatic use / tests
    tree.ms_extend = _extend
    tree.ms_select_all = _select_all


# ==========================================================================
# Main application
# ==========================================================================

DEFAULT_CONFIG = {
    "ui_language": "en",
    "whisper_path": "",
    "ffmpeg_path": "",
    "markitdown_python": "",
    "audio_lang_code": "pt",
    "audio_langs": list(DEFAULT_AUDIO_LANGS),
    "model_cli": "turbo",
    "task": "transcribe",
    "output_formats": {f: True for f in OUTPUT_FORMATS},
    "output_dir_mode": "same",
    "fixed_output_dir": "",
    "selected_dictionary": "",
    "youtube_pref_lang": "auto",
    "youtube_keep_srt": True,
    "youtube_keep_txt": True,
    "youtube_output_dir": "",
    # v0.8.0
    "download_resolution": "best",
    "download_audio_only": False,
    "download_audio_format": "mp3",
    "download_container": "mp4",
    "download_output_dir": "",
    "speed_factor_by_model": {},
    "yt_per_video_seconds": YT_PER_VIDEO_DEFAULT,
    "md_per_file_seconds": MD_PER_FILE_DEFAULT,
    # v0.9.0 — pause control
    "youtube_pause_enabled": False,
    "youtube_pause_every": 20,
    "youtube_pause_minutes": 5,
    "download_pause_enabled": False,
    "download_pause_every": 20,
    "download_pause_minutes": 5,
    # v0.9.0 — transcribe after download (uses its own Whisper settings)
    "download_transcribe": False,
    "download_whisper_defined": False,
    "download_whisper_model": "",
    "download_whisper_lang": "pt",
    "download_whisper_dictionary": "",
    "grabber_output_mode": "title_link",
}

_OLD_AUDIO_LANG_MAP = {"portuguese": "pt", "english": "en",
                       "spanish": "es", "auto": "auto"}


class TranscriptLabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_config_dir()
        self.cfg = self._load_config()
        self.lang = self.cfg.get("ui_language", "en")
        if self.lang not in TRANSLATIONS:
            self.lang = "en"
        self.s = TRANSLATIONS[self.lang]

        self.dictionaries = load_json(DICTIONARIES_FILE, {})

        # runtime state
        self.queue_items = []
        self.live_queue = None
        self.md_queue_items = []
        self.worker = None
        self.stop_flag = None
        self.event_queue = queue.Queue()
        self.is_running = False
        self.md_worker = None
        self.md_stop_flag = None
        self.md_event_queue = queue.Queue()
        self.md_is_running = False
        self.youtube_queue_items = []
        self.youtube_worker = None
        self.youtube_stop_flag = None
        self.youtube_event_queue = queue.Queue()
        self.youtube_is_running = False
        # download tab
        self.download_queue_items = []
        self.dl_live_queue = None
        self.download_worker = None
        self.download_stop_flag = None
        self.download_event_queue = queue.Queue()
        self.download_is_running = False
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_cur_running_id = None
        # grabber tab
        self.grabber_worker = None
        self.grabber_stop_flag = None
        self.grabber_event_queue = queue.Queue()
        self.grabber_is_running = False
        self._grab_entries = []
        # playlist expansion workers (keyed lists, polled via the owning tab queue)
        self._expand_workers = []
        # async length probe
        self._probe_event_queue = queue.Queue()
        self._probe_threads = []
        self._yt_controls = []
        self._yt_done = 0
        self._yt_errors = 0
        self._yt_cur_index = 0
        self._wrap_labels = []
        self._batch_start_time = None
        self._batch_done = 0
        self._batch_errors = 0
        self._cur_duration = None
        self._cur_phase = None
        self._trans_total_seconds = 0.0
        self._trans_done_seconds = 0.0
        self._cur_position = 0.0
        self._cur_index = 0
        self._md_batch_start_time = None
        self._md_done = 0
        self._md_errors = 0
        self._md_cur_index = 0

        # dependency detection
        self._detect_dependencies()

        self.title(self.s["window_title"])
        self.geometry("1060x1042")
        self.minsize(760, 600)
        self._set_icon()

        self._build_menubar()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll_events)
        self.after(120, self._poll_md_events)
        self.after(120, self._poll_youtube_events)
        self.after(120, self._poll_download_events)
        self.after(120, self._poll_grabber_events)
        self.after(150, self._poll_probe_events)

    # ---- helpers ---------------------------------------------------------
    def t(self, key, **kw):
        text = self.s.get(key, key)
        if kw:
            try:
                return text.format(**kw)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def _load_config(self):
        data = load_json(CONFIG_FILE, {})
        cfg = dict(DEFAULT_CONFIG)
        cfg["output_formats"] = dict(DEFAULT_CONFIG["output_formats"])
        cfg["audio_langs"] = list(DEFAULT_AUDIO_LANGS)
        cfg["speed_factor_by_model"] = {}
        if isinstance(data, dict):
            # migrate old audio_lang_key
            if "audio_lang_code" not in data and "audio_lang_key" in data:
                data["audio_lang_code"] = _OLD_AUDIO_LANG_MAP.get(
                    data.get("audio_lang_key"), "pt")
            for k, v in data.items():
                if k == "output_formats" and isinstance(v, dict):
                    merged = dict(DEFAULT_CONFIG["output_formats"])
                    merged.update({fk: bool(fv) for fk, fv in v.items()
                                   if fk in OUTPUT_FORMATS})
                    cfg["output_formats"] = merged
                elif k in DEFAULT_CONFIG:
                    cfg[k] = v
        if not isinstance(cfg.get("speed_factor_by_model"), dict):
            cfg["speed_factor_by_model"] = {}
        if cfg.get("download_resolution") not in DOWNLOAD_RESOLUTIONS:
            cfg["download_resolution"] = "best"
        if cfg.get("download_audio_format") not in DOWNLOAD_AUDIO_FORMATS:
            cfg["download_audio_format"] = "mp3"
        if cfg.get("download_container") not in DOWNLOAD_CONTAINERS:
            cfg["download_container"] = "mp4"
        # sanity
        if cfg.get("audio_lang_code") not in (
                list(AUDIO_LANG_OPTIONS) + list(WHISPER_LANGUAGES)):
            cfg["audio_lang_code"] = "pt"
        langs = cfg.get("audio_langs") or list(DEFAULT_AUDIO_LANGS)
        cfg["audio_langs"] = [c for c in langs
                              if c in AUDIO_LANG_OPTIONS or c in WHISPER_LANGUAGES]
        if not cfg["audio_langs"]:
            cfg["audio_langs"] = list(DEFAULT_AUDIO_LANGS)
        if cfg["audio_lang_code"] not in cfg["audio_langs"]:
            cfg["audio_langs"].insert(0, cfg["audio_lang_code"])
        return cfg

    def _save_config(self):
        save_json(CONFIG_FILE, self.cfg)

    def _detect_dependencies(self):
        self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
        self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
        self.python_exe = markitdown_python(self.cfg)
        self.markitdown_ok = markitdown_is_available(self.python_exe)
        self.ytdlp_ok = ytdlp_is_available(self.python_exe)

    def _set_icon(self):
        try:
            import base64
            self._icon_img_small = tk.PhotoImage(data=base64.b64decode(APP_ICON_SMALL_BASE64))
            self.iconphoto(True, self._icon_img_small)
        except Exception:
            self._icon_img_small = None
        try:
            import base64
            self._icon_img_large = tk.PhotoImage(data=base64.b64decode(APP_ICON_LARGE_BASE64))
        except Exception:
            self._icon_img_large = None

    # ---- audio language display/param -----------------------------------
    def _audio_lang_display(self, code):
        if code == "auto":
            return self.t("audlang_auto")
        if code == "pt":
            return self.t("audlang_portuguese")
        if code == "en":
            return self.t("audlang_english")
        if code == "es":
            return self.t("audlang_spanish")
        name = WHISPER_LANGUAGES.get(code, code)
        return f"{name} ({code})"

    def _model_display(self, cli):
        info = MODEL_INFO[cli]
        return f"{cli}  —  {self.t(info['desc_key'])}"

    # ======================================================================
    # Menubar
    # ======================================================================
    def _build_menubar(self):
        menubar = tk.Menu(self)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label=self.t("menu_whisper"),
                                  command=self._open_whisper_settings)
        settings_menu.add_command(label=self.t("menu_markitdown"),
                                  command=self._open_markitdown_settings)
        settings_menu.add_command(label=self.t("menu_ytdlp"),
                                  command=self._open_ytdlp_settings)
        settings_menu.add_command(label=self.t("menu_ffmpeg"),
                                  command=self._open_ffmpeg_settings)
        settings_menu.add_command(label=self.t("menu_output_formats"),
                                  command=self._open_output_formats)
        settings_menu.add_separator()
        lang_menu = tk.Menu(settings_menu, tearoff=0)
        self._menu_lang_var = tk.StringVar(value=self.lang)
        lang_menu.add_radiobutton(label=self.t("lang_english"), value="en",
                                  variable=self._menu_lang_var,
                                  command=lambda: self._switch_language("en"))
        lang_menu.add_radiobutton(label=self.t("lang_portuguese"), value="pt",
                                  variable=self._menu_lang_var,
                                  command=lambda: self._switch_language("pt"))
        settings_menu.add_cascade(label=self.t("menu_interface_language"),
                                  menu=lang_menu)
        menubar.add_cascade(label=self.t("menu_settings"), menu=settings_menu)
        menubar.add_command(label=self.t("menu_about"), command=self._open_about)
        self.config(menu=menubar)

    # ======================================================================
    # UI build
    # ======================================================================
    def _build_ui(self):
        if hasattr(self, "notebook") and self.notebook.winfo_exists():
            self.notebook.destroy()
        if hasattr(self, "_header_bar") and self._header_bar.winfo_exists():
            self._header_bar.destroy()
        self._style_notebook_tabs()
        self._wrap_labels = []

        self._header_bar = ttk.Frame(self)
        self._header_bar.pack(fill="x", padx=10, pady=(8, 0))
        if getattr(self, "_icon_img_small", None) is not None:
            ttk.Label(self._header_bar, image=self._icon_img_small).pack(side="left", padx=(0, 6))
        ttk.Label(self._header_bar, text=APP_NAME,
                  font=("TkDefaultFont", 12, "bold")).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_md = ttk.Frame(self.notebook)
        self.tab_youtube = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.tab_dict = ttk.Frame(self.notebook)
        self.tab_grabber = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=self.t("tab_transcription"))
        self.notebook.add(self.tab_md, text=self.t("tab_md"))
        self.notebook.add(self.tab_youtube, text=self.t("tab_youtube"))
        self.notebook.add(self.tab_download, text=self.t("tab_download"))
        self.notebook.add(self.tab_dict, text=self.t("tab_dictionary"))
        self.notebook.add(self.tab_grabber, text=self.t("tab_grabber"))

        self._build_transcription_tab(self.tab_main)
        self._build_md_tab(self.tab_md)
        self._build_youtube_tab(self.tab_youtube)
        self._build_download_tab(self.tab_download)
        self._build_dictionary_tab(self.tab_dict)
        self._build_grabber_tab(self.tab_grabber)
        self._refresh_status_indicators()
        self._refresh_audio_lang_dropdown()
        self._refresh_model_dropdown()
        self._refresh_dictionary_dropdown()
        self._update_clip_gate()
        self._refresh_youtube_enabled()
        self._refresh_download_enabled()
        self._update_trans_summary()
        self._update_md_summary()
        self._update_youtube_summary()
        self._update_download_summary()

    def _register_wrap(self, label):
        self._wrap_labels.append(label)

    def _style_notebook_tabs(self):
        """Make the active tab clearly stand out (bold + accent + tint + padding).
        On Windows native themes the background tint may be ignored, but the bold
        accent text still distinguishes the selected tab."""
        try:
            style = ttk.Style()
            base_font = tkfont.nametofont("TkDefaultFont")
            self._tab_font_normal = (base_font.actual("family"), base_font.actual("size"))
            self._tab_font_bold = (base_font.actual("family"),
                                   base_font.actual("size"), "bold")
            style.configure("TNotebook", tabmargins=(2, 5, 2, 0))
            style.configure("TNotebook.Tab", padding=(14, 7),
                            font=self._tab_font_normal)
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#ffffff"), ("active", "#eef3fb"),
                            ("!selected", "#dde1e7")],
                foreground=[("selected", "#0a58ca"), ("!selected", "#444444")],
                font=[("selected", self._tab_font_bold),
                      ("!selected", self._tab_font_normal)],
                expand=[("selected", (1, 1, 1, 0))])
        except Exception:
            pass

    # ---- transcription tab ----------------------------------------------
    def _build_transcription_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        scroll.canvas.bind("<Configure>", self._on_main_canvas_configure, add="+")
        self._main_canvas = scroll.canvas
        r = 0

        # --- status indicators (row 1) ---
        status = ttk.LabelFrame(root, text="")
        status.grid(row=r, column=0, sticky="ew", padx=6, pady=(6, 2))
        status.columnconfigure(3, weight=1)
        self.ind_whisper = tk.Label(status, text="", cursor="hand2",
                                    font=("TkDefaultFont", 10, "bold"))
        self.ind_whisper.grid(row=0, column=0, padx=8, pady=6)
        self.ind_whisper.bind("<Button-1>", lambda e: self._open_whisper_settings())
        self.ind_markitdown = tk.Label(status, text="", cursor="hand2",
                                       font=("TkDefaultFont", 10, "bold"))
        self.ind_markitdown.grid(row=0, column=1, padx=8, pady=6)
        self.ind_markitdown.bind("<Button-1>", lambda e: self._open_markitdown_settings())
        self.ind_ffmpeg = tk.Label(status, text="", cursor="hand2",
                                   font=("TkDefaultFont", 10, "bold"))
        self.ind_ffmpeg.grid(row=0, column=2, padx=8, pady=6)
        self.ind_ffmpeg.bind("<Button-1>", lambda e: self._open_ffmpeg_settings())
        self.ind_hint = ttk.Label(status, text=self.t("dep_hint"), foreground="#777")
        self.ind_hint.grid(row=0, column=3, sticky="e", padx=8)
        r += 1

        # --- audio language + model row ---
        cfgf = ttk.Frame(root)
        cfgf.grid(row=r, column=0, sticky="ew", padx=6, pady=2)
        cfgf.columnconfigure(1, weight=1)
        cfgf.columnconfigure(4, weight=1)
        ttk.Label(cfgf, text=self.t("audio_language")).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=4)
        self.audio_lang_var = tk.StringVar()
        self.audio_lang_combo = ttk.Combobox(cfgf, textvariable=self.audio_lang_var,
                                              state="readonly", width=22)
        self.audio_lang_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.audio_lang_combo.bind("<<ComboboxSelected>>", self._on_audio_lang_change)
        ttk.Button(cfgf, text=self.t("add_languages"),
                   command=lambda: self._open_whisper_settings(focus="langs")
                   ).grid(row=0, column=2, sticky="w", padx=(6, 16), pady=4)

        ttk.Label(cfgf, text=self.t("ai_model")).grid(row=0, column=3, sticky="w", padx=(0, 4), pady=4)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(cfgf, textvariable=self.model_var,
                                        state="readonly", width=34)
        self.model_combo.grid(row=0, column=4, sticky="ew", pady=4)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)
        ttk.Button(cfgf, text=self.t("add_model"),
                   command=lambda: self._open_whisper_settings(focus="models")
                   ).grid(row=0, column=5, sticky="w", padx=(6, 0), pady=4)

        # task row
        ttk.Label(cfgf, text=self.t("task")).grid(row=1, column=0, sticky="w", padx=(0, 4), pady=4)
        self.task_var = tk.StringVar()
        self.task_combo = ttk.Combobox(cfgf, textvariable=self.task_var,
                                       state="readonly", width=22)
        self.task_combo["values"] = [self.t("task_transcribe"), self.t("task_translate")]
        self.task_combo.current(0 if self.cfg.get("task", "transcribe") == "transcribe" else 1)
        self.task_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.task_combo.bind("<<ComboboxSelected>>", self._on_task_change)
        r += 1

        # model status label
        self.model_status_var = tk.StringVar(value="")
        msl = ttk.Label(root, textvariable=self.model_status_var, foreground="#555")
        msl.grid(row=r, column=0, sticky="w", padx=10, pady=(0, 4))
        self._register_wrap(msl)
        r += 1

        # vocabulary dictionary
        dictf = ttk.Frame(root)
        dictf.grid(row=r, column=0, sticky="ew", padx=6, pady=2)
        dictf.columnconfigure(1, weight=1)
        ttk.Label(dictf, text=self.t("vocab_dict")).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.dict_var = tk.StringVar()
        self.dict_combo = ttk.Combobox(dictf, textvariable=self.dict_var,
                                       state="readonly", width=34)
        self.dict_combo.grid(row=0, column=1, sticky="ew")
        r += 1

        # clip frame
        self.clip_frame = ttk.LabelFrame(root, text=self.t("clip_frame"))
        self.clip_frame.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        self.clip_frame.columnconfigure(5, weight=1)
        self.clip_enabled_var = tk.BooleanVar(value=False)
        self.clip_check = ttk.Checkbutton(self.clip_frame, text=self.t("clip_enable"),
                                          variable=self.clip_enabled_var,
                                          command=self._update_clip_gate)
        self.clip_check.grid(row=0, column=0, columnspan=6, sticky="w", padx=6, pady=(4, 0))
        ttk.Label(self.clip_frame, text=self.t("clip_start")).grid(row=1, column=0, sticky="w", padx=(6, 2), pady=4)
        self.clip_start_var = tk.StringVar(value="0:00:00")
        self.clip_start_entry = ttk.Entry(self.clip_frame, textvariable=self.clip_start_var, width=12)
        self.clip_start_entry.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(self.clip_frame, text=self.t("clip_end")).grid(row=1, column=2, sticky="w", padx=(12, 2), pady=4)
        self.clip_end_var = tk.StringVar(value="0:05:00")
        self.clip_end_entry = ttk.Entry(self.clip_frame, textvariable=self.clip_end_var, width=12)
        self.clip_end_entry.grid(row=1, column=3, sticky="w", pady=4)
        self.clip_hint_label = ttk.Label(self.clip_frame, text=self.t("clip_hint"), foreground="#777")
        self.clip_hint_label.grid(row=2, column=0, columnspan=6, sticky="w", padx=6, pady=(0, 4))
        self._register_wrap(self.clip_hint_label)
        r += 1

        # output folder
        outf = ttk.LabelFrame(root, text=self.t("output_folder"))
        outf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        outf.columnconfigure(1, weight=1)
        self.outdir_mode_var = tk.StringVar(value=self.cfg.get("output_dir_mode", "same"))
        ttk.Radiobutton(outf, text=self.t("same_folder"), variable=self.outdir_mode_var,
                        value="same", command=self._on_outdir_mode_change
                        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 0))
        ttk.Radiobutton(outf, text=self.t("fixed_folder"), variable=self.outdir_mode_var,
                        value="fixed", command=self._on_outdir_mode_change
                        ).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.fixed_dir_var = tk.StringVar(value=self.cfg.get("fixed_output_dir", ""))
        self.fixed_dir_entry = ttk.Entry(outf, textvariable=self.fixed_dir_var)
        self.fixed_dir_entry.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(outf, text=self.t("browse"),
                   command=self._browse_fixed_dir).grid(row=1, column=2, padx=6, pady=4)
        r += 1

        # queue
        qf = ttk.LabelFrame(root, text=self.t("queue_frame"))
        qf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        qf.columnconfigure(0, weight=1)
        btns = ttk.Frame(qf)
        btns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(btns, text=self.t("add_files"), command=self._add_files).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("remove_selected"), command=self._remove_selected).pack(side="left", padx=2)
        self.clear_queue_btn = ttk.Button(btns, text=self.t("clear_queue"), command=self._clear_queue)
        self.clear_queue_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_up"), command=lambda: self._move_selected(-1)).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_down"), command=lambda: self._move_selected(1)).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "length", "status")
        qwrap, self.tree, _qsb = make_scrollable_queue(qf, cols, height=8)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        qf.rowconfigure(1, weight=1)
        self.tree.heading("order", text=self.t("col_order"))
        self.tree.heading("file", text=self.t("col_file"))
        self.tree.heading("folder", text=self.t("col_folder"))
        self.tree.heading("length", text=self.t("col_length"))
        self.tree.heading("status", text=self.t("col_status"))
        self.tree.column("order", width=40, anchor="center", stretch=False)
        self.tree.column("file", width=300)
        self.tree.column("folder", width=230)
        self.tree.column("length", width=90, anchor="center", stretch=False)
        self.tree.column("status", width=120, anchor="center")
        self.trans_summary_var = tk.StringVar(value="")
        tsum = ttk.Label(qf, textvariable=self.trans_summary_var, foreground="#444")
        tsum.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))
        self._register_wrap(tsum)
        r += 1

        # run controls
        runf = ttk.Frame(root)
        runf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        runf.columnconfigure(2, weight=1)
        self.start_btn = ttk.Button(runf, text=self.t("start_batch"), command=self._start_batch)
        self.start_btn.grid(row=0, column=0, padx=2)
        self.cancel_btn = ttk.Button(runf, text=self.t("cancel"), command=self._cancel_batch, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=2)
        self.open_out_btn = ttk.Button(runf, text=self.t("open_output_folder"),
                                       command=self._open_output_folder, state="disabled")
        self.open_out_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.progress = TwoToneProgress(runf, height=22)
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.progress_pct_var = tk.StringVar(value="")
        self.progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        pll = ttk.Label(runf, textvariable=self.progress_label_var, foreground="#555")
        pll.grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))
        self._register_wrap(pll)
        r += 1

        # log
        logf = ttk.LabelFrame(root, text=self.t("log_frame"))
        logf.grid(row=r, column=0, sticky="nsew", padx=6, pady=4)
        logf.columnconfigure(0, weight=1)
        self.log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                font=("TkFixedFont", 9))
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=logsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        logsb.grid(row=0, column=1, sticky="ns", pady=4)
        self.log_frame_label = logf
        note = ttk.Label(logf, text=self.t("partial_output_note"), foreground="#777")
        note.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        self._register_wrap(note)

    def _on_main_canvas_configure(self, event):
        width = max(200, event.width - 40)
        for lbl in self._wrap_labels:
            try:
                lbl.configure(wraplength=width)
            except tk.TclError:
                pass

    # ---- MD File Generation tab -----------------------------------------
    def _build_md_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)   # queue expands; log is capped

        intro = ttk.Label(root, text=self.t("md_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        intro.configure(wraplength=900)
        self._md_intro_label = intro

        # output folder
        outf = ttk.LabelFrame(root, text=self.t("output_folder"))
        outf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        outf.columnconfigure(1, weight=1)
        self.md_outdir_mode_var = tk.StringVar(value="same")
        ttk.Radiobutton(outf, text=self.t("same_folder"), variable=self.md_outdir_mode_var,
                        value="same").grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 0))
        ttk.Radiobutton(outf, text=self.t("fixed_folder"), variable=self.md_outdir_mode_var,
                        value="fixed").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.md_fixed_dir_var = tk.StringVar(value="")
        ttk.Entry(outf, textvariable=self.md_fixed_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(outf, text=self.t("browse"),
                   command=self._browse_md_fixed_dir).grid(row=1, column=2, padx=6, pady=4)

        # queue (prominent, scrollable)
        qf = ttk.LabelFrame(root, text=self.t("md_queue_frame"))
        qf.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        btns = ttk.Frame(qf)
        btns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(btns, text=self.t("add_files"), command=self._md_add_files).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("remove_selected"), command=self._md_remove_selected).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("clear_queue"), command=self._md_clear_queue).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "size", "status")
        qwrap, self.md_tree, _msb = make_scrollable_queue(qf, cols, height=18)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.md_tree.heading("order", text=self.t("col_order"))
        self.md_tree.heading("file", text=self.t("col_file"))
        self.md_tree.heading("folder", text=self.t("col_folder"))
        self.md_tree.heading("size", text=self.t("md_col_size"))
        self.md_tree.heading("status", text=self.t("col_status"))
        self.md_tree.column("order", width=40, anchor="center", stretch=False)
        self.md_tree.column("file", width=300)
        self.md_tree.column("folder", width=230)
        self.md_tree.column("size", width=90, anchor="center", stretch=False)
        self.md_tree.column("status", width=120, anchor="center")
        self.md_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.md_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # run controls
        runf = ttk.Frame(root)
        runf.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        runf.columnconfigure(2, weight=1)
        self.md_start_btn = ttk.Button(runf, text=self.t("start_batch_md"), command=self._start_md_batch)
        self.md_start_btn.grid(row=0, column=0, padx=2)
        self.md_cancel_btn = ttk.Button(runf, text=self.t("cancel"), command=self._cancel_md_batch, state="disabled")
        self.md_cancel_btn.grid(row=0, column=1, padx=2)
        self.md_open_out_btn = ttk.Button(runf, text=self.t("open_output_folder"),
                                          command=self._md_open_output_folder, state="disabled")
        self.md_open_out_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.md_progress = TwoToneProgress(runf, height=22)
        self.md_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.md_progress_pct_var = tk.StringVar(value="")
        self.md_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(runf, textvariable=self.md_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log (secondary, capped)
        logf = ttk.LabelFrame(root, text=self.t("log_frame_md"))
        logf.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.md_log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.md_log_text.yview)
        self.md_log_text.configure(yscrollcommand=logsb.set)
        self.md_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        logsb.grid(row=0, column=1, sticky="ns", pady=4)

    # ---- YouTube Transcription tab --------------------------------------
    def _build_youtube_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(5, weight=1)   # queue row expands; log is capped
        self._yt_controls = []

        # status indicators (MarkItDown + yt-dlp), clickable
        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(2, weight=1)
        self.yt_ind_markitdown = tk.Label(status, text="", cursor="hand2",
                                          font=("TkDefaultFont", 10, "bold"))
        self.yt_ind_markitdown.grid(row=0, column=0, padx=8, pady=6)
        self.yt_ind_markitdown.bind("<Button-1>", lambda e: self._open_markitdown_settings())
        self.yt_ind_ytdlp = tk.Label(status, text="", cursor="hand2",
                                     font=("TkDefaultFont", 10, "bold"))
        self.yt_ind_ytdlp.grid(row=0, column=1, padx=8, pady=6)
        self.yt_ind_ytdlp.bind("<Button-1>", lambda e: self._open_ytdlp_settings())
        ttk.Label(status, text=self.t("dep_hint"), foreground="#777"
                  ).grid(row=0, column=2, sticky="e", padx=8)

        intro = ttk.Label(root, text=self.t("yt_intro"), foreground="#555")
        intro.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 0))
        intro.configure(wraplength=900)
        self.yt_required_note = ttk.Label(root, text=self.t("yt_md_required_note"),
                                          foreground="#cf222e")
        self.yt_required_note.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 0))
        self.yt_required_note.configure(wraplength=900)

        body = ttk.Frame(root)
        body.grid(row=3, column=0, sticky="ew", padx=8, pady=2)
        body.columnconfigure(0, weight=1)
        langrow = ttk.Frame(body)
        langrow.grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Label(langrow, text=self.t("yt_pref_lang")).pack(side="left")
        self.yt_lang_var = tk.StringVar()
        self.yt_lang_combo = ttk.Combobox(langrow, textvariable=self.yt_lang_var,
                                          state="readonly", width=28)
        self.yt_lang_combo.pack(side="left", padx=6)
        self.yt_lang_combo.bind("<<ComboboxSelected>>", self._on_yt_lang_change)
        self._yt_controls.append(self.yt_lang_combo)

        # Fixed output folder (above the queue, matching the other tabs)
        of = ttk.LabelFrame(root, text=self.t("fixed_folder"))
        of.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        of.columnconfigure(0, weight=1)
        self.yt_outdir_var = tk.StringVar(value=self.cfg.get("youtube_output_dir") or str(Path.home()))
        yt_entry = ttk.Entry(of, textvariable=self.yt_outdir_var)
        yt_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        yt_browse = ttk.Button(of, text=self.t("browse"), command=self._yt_browse_outdir)
        yt_browse.grid(row=0, column=1, padx=6, pady=6)
        self._yt_controls += [yt_entry, yt_browse]

        qf = ttk.LabelFrame(root, text=self.t("yt_queue_frame"))
        qf.grid(row=5, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        qbtns = ttk.Frame(qf)
        qbtns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        b_add = ttk.Button(qbtns, text=self.t("btn_add"),
                           command=lambda: self._open_add_links_dialog("youtube"))
        b_add.pack(side="left", padx=2)
        b_rm = ttk.Button(qbtns, text=self.t("remove_selected"), command=self._yt_remove_selected)
        b_rm.pack(side="left", padx=2)
        b_cl = ttk.Button(qbtns, text=self.t("clear_queue"), command=self._yt_clear_queue)
        b_cl.pack(side="left", padx=2)
        b_up = ttk.Button(qbtns, text=self.t("move_up"),
                          command=lambda: self._yt_move_selected(-1))
        b_up.pack(side="left", padx=2)
        b_dn = ttk.Button(qbtns, text=self.t("move_down"),
                          command=lambda: self._yt_move_selected(1))
        b_dn.pack(side="left", padx=2)
        self._yt_controls += [b_add, b_rm, b_cl, b_up, b_dn]
        cols = ("order", "video", "length", "status")
        qwrap, self.yt_tree, _ysb2 = make_scrollable_queue(qf, cols, height=14)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.yt_tree.heading("order", text=self.t("col_order"))
        self.yt_tree.heading("video", text=self.t("yt_col_video"))
        self.yt_tree.heading("length", text=self.t("col_length"))
        self.yt_tree.heading("status", text=self.t("col_status"))
        self.yt_tree.column("order", width=40, anchor="center", stretch=False)
        self.yt_tree.column("video", width=460)
        self.yt_tree.column("length", width=90, anchor="center", stretch=False)
        self.yt_tree.column("status", width=160, anchor="center")
        self.yt_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.yt_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        opt = ttk.Frame(root)
        opt.grid(row=6, column=0, sticky="ew", padx=10, pady=2)
        self.yt_srt_var = tk.BooleanVar(value=self.cfg.get("youtube_keep_srt", True))
        self.yt_txt_var = tk.BooleanVar(value=self.cfg.get("youtube_keep_txt", True))
        c_srt = ttk.Checkbutton(opt, text=self.t("yt_keep_srt"), variable=self.yt_srt_var,
                                command=self._on_yt_opts_change)
        c_srt.grid(row=0, column=0, sticky="w", padx=(0, 16))
        c_txt = ttk.Checkbutton(opt, text=self.t("yt_keep_txt"), variable=self.yt_txt_var,
                                command=self._on_yt_opts_change)
        c_txt.grid(row=0, column=1, sticky="w")
        self._yt_controls += [c_srt, c_txt]

        info = ttk.Label(root, text=self.t("yt_output_info") + "  " + self.t("yt_settings_note"),
                         foreground="#555")
        info.grid(row=7, column=0, sticky="w", padx=10, pady=(2, 2))
        info.configure(wraplength=900)

        self._build_pause_box(root, "yt").grid(row=8, column=0, sticky="ew", padx=8, pady=2)

        rf = ttk.Frame(root)
        rf.grid(row=9, column=0, sticky="ew", padx=8, pady=4)
        rf.columnconfigure(2, weight=1)
        self.yt_start_btn = ttk.Button(rf, text=self.t("yt_start"), command=self._start_youtube_batch)
        self.yt_start_btn.grid(row=0, column=0, padx=2)
        self.yt_cancel_btn = ttk.Button(rf, text=self.t("cancel"), command=self._cancel_youtube_batch,
                                        state="disabled")
        self.yt_cancel_btn.grid(row=0, column=1, padx=2)
        self.yt_open_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                      command=self._yt_open_output, state="disabled")
        self.yt_open_btn.grid(row=0, column=3, padx=2, sticky="e")
        self._yt_controls.append(self.yt_start_btn)
        self.yt_progress = TwoToneProgress(rf, height=22)
        self.yt_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.yt_progress_pct_var = tk.StringVar(value="")
        self.yt_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.yt_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        lf = ttk.LabelFrame(root, text=self.t("yt_log_frame"))
        lf.grid(row=10, column=0, sticky="ew", padx=8, pady=4)
        lf.columnconfigure(0, weight=1)
        self.yt_log_text = tk.Text(lf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        ysb = ttk.Scrollbar(lf, orient="vertical", command=self.yt_log_text.yview)
        self.yt_log_text.configure(yscrollcommand=ysb.set)
        self.yt_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        ysb.grid(row=0, column=1, sticky="ns", pady=4)

        self._refresh_youtube_lang_dropdown()
        self._render_youtube_queue()

    def _refresh_youtube_lang_dropdown(self):
        codes = ["auto"] + [c for c in self.cfg.get("audio_langs", []) if c != "auto"]
        # dedupe preserving order
        seen = set()
        codes = [c for c in codes if not (c in seen or seen.add(c))]
        displays = []
        self._yt_code_by_display = {}
        for c in codes:
            disp = self.t("yt_lang_auto") if c == "auto" else self._audio_lang_display(c)
            displays.append(disp)
            self._yt_code_by_display[disp] = c
        self.yt_lang_combo["values"] = displays
        cur = self.cfg.get("youtube_pref_lang", "auto")
        if cur not in codes:
            cur = "auto"
            self.cfg["youtube_pref_lang"] = cur
        disp = self.t("yt_lang_auto") if cur == "auto" else self._audio_lang_display(cur)
        self.yt_lang_var.set(disp)

    def _on_yt_lang_change(self, _event=None):
        code = getattr(self, "_yt_code_by_display", {}).get(self.yt_lang_var.get(), "auto")
        self.cfg["youtube_pref_lang"] = code
        self._save_config()

    def _on_yt_opts_change(self):
        self.cfg["youtube_keep_srt"] = self.yt_srt_var.get()
        self.cfg["youtube_keep_txt"] = self.yt_txt_var.get()
        self._save_config()

    def _yt_browse_outdir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.yt_outdir_var.set(d)
            self.cfg["youtube_output_dir"] = d
            self._save_config()

    def _refresh_youtube_enabled(self):
        """Grey out the whole tab when MarkItDown is missing."""
        if not hasattr(self, "yt_ind_markitdown"):
            return
        ok = bool(self.markitdown_ok)
        mark = self.t("dep_found") if ok else self.t("dep_missing")
        self.yt_ind_markitdown.configure(text=f"{self.t('dep_markitdown')} {mark}",
                                         fg=("#1a7f37" if ok else "#cf222e"))
        if hasattr(self, "yt_ind_ytdlp"):
            yok = bool(getattr(self, "ytdlp_ok", False))
            ymark = self.t("dep_found") if yok else self.t("dep_missing")
            self.yt_ind_ytdlp.configure(text=f"{self.t('dep_ytdlp')} {ymark}",
                                        fg=("#1a7f37" if yok else "#cf222e"))
        for w in self._yt_controls:
            try:
                if isinstance(w, ttk.Combobox):
                    w.configure(state="readonly" if ok else "disabled")
                else:
                    w.configure(state="normal" if ok else "disabled")
            except tk.TclError:
                pass
        # cancel/open buttons follow run state, not gating
        try:
            self.yt_required_note.grid() if not ok else self.yt_required_note.grid_remove()
        except tk.TclError:
            pass

    # --- YouTube queue ops ---
    def _open_add_links_dialog(self, target):
        # Per item 1, only the YouTube Transcription tab keeps the queue
        # locked during processing; the Download tab allows live editing.
        if target == "youtube" and self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        win = tk.Toplevel(self)
        win.title(self.t("add_dialog_title"))
        win.transient(self)
        win.geometry("600x340")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("add_dialog_info"), foreground="#555",
                  wraplength=560, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))
        txt = tk.Text(frm, height=10, wrap="word", font=("TkFixedFont", 9))
        txt.grid(row=1, column=0, sticky="nsew")
        txt.focus_set()
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e", pady=(8, 0))

        def do_add():
            raw = txt.get("1.0", "end")
            if raw.strip():
                self._ingest_and_report(raw, target)
            win.destroy()
        ttk.Button(btns, text=self.t("btn_add"), command=do_add).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("cancel"), command=win.destroy).pack(side="left", padx=2)

    def _ingest_and_report(self, raw, target):
        items = self.youtube_queue_items if target == "youtube" else self.download_queue_items
        added, invalid, playlists = self._ingest_links(raw, items, target=target)
        if target == "youtube":
            self._render_youtube_queue(); self._update_youtube_summary()
        else:
            self._render_download_queue(); self._update_download_summary()
        if playlists == 0 and added == 0 and invalid == 0:
            messagebox.showinfo(self.t("info"), self.t("info_all_in_queue"))
        elif added == 0 and invalid and playlists == 0:
            messagebox.showwarning(self.t("warn"), self.t("yt_no_valid_links"))
        elif invalid:
            messagebox.showinfo(self.t("info"), self.t("yt_some_invalid", n=invalid))
        return added, invalid, playlists

    def _yt_move_selected(self, direction):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        sel = self.yt_tree.selection()
        if not sel:
            return
        idx = int(sel[0]); new = idx + direction
        if 0 <= new < len(self.youtube_queue_items):
            self.youtube_queue_items[idx], self.youtube_queue_items[new] = \
                self.youtube_queue_items[new], self.youtube_queue_items[idx]
            self._render_youtube_queue()
            self.yt_tree.selection_set(str(new))

    def _yt_remove_selected(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for iid in self.yt_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.youtube_queue_items):
                self.youtube_queue_items[idx] = None
        self.youtube_queue_items = [it for it in self.youtube_queue_items if it is not None]
        self._render_youtube_queue()
        self._update_youtube_summary()

    def _yt_clear_queue(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.youtube_queue_items = []
        self._render_youtube_queue()
        self._update_youtube_summary()

    def _yt_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_yt"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_youtube_queue(self):
        if not hasattr(self, "yt_tree"):
            return
        self.yt_tree.delete(*self.yt_tree.get_children())
        for i, it in enumerate(self.youtube_queue_items):
            label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                else self._yt_status_text(it.status)
            length = fmt_hms(it.duration) if it.duration else "…"
            self.yt_tree.insert("", "end", iid=str(i),
                                values=(i + 1, it.filename, length, label))

    def _yt_open_output(self):
        for it in self.youtube_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return
        if self.yt_outdir_var.get():
            self._open_path(self.yt_outdir_var.get())

    # --- YouTube run ---
    def _start_youtube_batch(self):
        if self.youtube_is_running:
            return
        if not self.markitdown_ok:
            messagebox.showerror(self.t("error"), self.t("err_no_markitdown"))
            self._open_markitdown_settings()
            return
        if not self.youtube_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self._enforce_caps(len(self.youtube_queue_items),
                                  TRANSCRIBE_SOFT_CAP, TRANSCRIBE_HARD_CAP):
            return
        out_dir = self.yt_outdir_var.get().strip()
        if not out_dir:
            messagebox.showerror(self.t("error"), self.t("yt_need_output_dir"))
            return
        self.cfg["youtube_output_dir"] = out_dir
        self._save_config()
        for it in self.youtube_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_youtube_queue()
        code = self.cfg.get("youtube_pref_lang", "auto")
        preferred = None if code == "auto" else code
        prefix = ytdlp_command_prefix(self.python_exe) if self.ytdlp_ok else None
        every, pause_seconds = self._pause_params("yt")
        self.youtube_stop_flag = threading.Event()
        self.youtube_worker = YouTubeWorker(
            items=self.youtube_queue_items, preferred_code=preferred,
            keep_srt=self.yt_srt_var.get(), keep_txt=self.yt_txt_var.get(),
            output_dir=out_dir, strings=self.s, event_queue=self.youtube_event_queue,
            stop_flag=self.youtube_stop_flag, ytdlp_prefix=prefix,
            delay_range=YT_TRANSCRIBE_DELAY, lang=self.lang,
            pause_every=every, pause_seconds=pause_seconds)
        self.youtube_is_running = True
        self._yt_done = 0
        self._yt_errors = 0
        self._yt_cur_index = 0
        self._yt_total = len(self.youtube_queue_items)
        self.yt_start_btn.configure(state="disabled")
        self.yt_cancel_btn.configure(state="normal")
        self.yt_open_btn.configure(state="disabled")
        self._clear_log(self.yt_log_text)
        self._append_text(self.yt_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, 0.0)
        self.youtube_worker.start()

    def _cancel_youtube_batch(self):
        if self.youtube_is_running and self.youtube_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.yt_log_text, self.t("log_canceling"))
                self.youtube_stop_flag.set()

    def _poll_youtube_events(self):
        try:
            while True:
                ev = self.youtube_event_queue.get_nowait()
                self._handle_youtube_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_youtube_events)

    def _handle_youtube_event(self, ev):
        kind = ev.get("kind")
        if kind == "yt_log":
            self._append_text(self.yt_log_text, ev.get("text", ""))
        elif kind == "expand_done":
            self._apply_expanded_entries(ev.get("entries", []), "youtube")
        elif kind == "expand_error":
            short, _ = youtube_error_message(ev.get("cause", "generic"), self.s,
                                             raw=ev.get("raw", ""))
            self._append_text(self.yt_log_text,
                              self.t("yt_expand_error", e=short) + "\n")
        elif kind == "yt_progress_index":
            self._yt_cur_index = ev.get("index", 0)
            self._update_yt_progress_label()
        elif kind == "yt_item_status":
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.youtube_queue_items):
                self.youtube_queue_items[idx].status = status
                if ev.get("error"):
                    self.youtube_queue_items[idx].error_message = ev["error"]
                self.yt_tree.set(str(idx), "status",
                                 ev.get("error") or self._yt_status_text(status))
            if status in ST_TERMINAL:
                if status == ST_DONE:
                    self._yt_done += 1
                elif status == ST_ERROR:
                    self._yt_errors += 1
                self._update_yt_progress_label()
        elif kind == "yt_batch_blocked":
            messagebox.showwarning(self.t("yt_block_title"),
                                   ev.get("message") or self.t("yt_block_dialog"))
        elif kind == "yt_batch_finished":
            self._on_youtube_batch_finished()

    def _update_yt_progress_label(self):
        total = max(1, getattr(self, "_yt_total", 1))
        done = self._yt_done + self._yt_errors
        pct = compute_batch_percent(0, 0, 0, done, total)
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, pct)
        cur = current_processing_index(done, total, self.youtube_is_running)
        self.yt_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_youtube_batch_finished(self):
        self.youtube_is_running = False
        self.youtube_worker = None
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, 100.0)
        self.yt_start_btn.configure(state="normal" if self.markitdown_ok else "disabled")
        self.yt_cancel_btn.configure(state="disabled")
        self.yt_open_btn.configure(state="normal")
        self._append_text(self.yt_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.yt_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._yt_done, errors=self._yt_errors))
        if self._yt_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._yt_done, errors=self._yt_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._yt_done))

    # ======================================================================
    # v0.8.0 shared helpers
    # ======================================================================
    def _set_progress(self, bar, pct_var, pct):
        txt = self.t("pct_label", pct=int(round(pct)))
        try:
            bar.set_percent(pct, text=txt)
        except Exception:
            try:
                bar.configure(value=max(0.0, min(100.0, float(pct))))
            except Exception:
                pass
        if pct_var is not None:
            pct_var.set(txt)

    @staticmethod
    def _human_bytes(n):
        if n is None:
            return "—"
        try:
            n = float(n)
        except (TypeError, ValueError):
            return "—"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                if unit == "B":
                    return f"{int(n)} {unit}"
                return f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    # ---- pause-every-N control (both YouTube tabs) -----------------------
    def _build_pause_box(self, parent, kind):
        pre = "youtube" if kind == "yt" else "download"
        en = tk.BooleanVar(value=bool(self.cfg.get(f"{pre}_pause_enabled", False)))
        every = tk.StringVar(value=str(self.cfg.get(f"{pre}_pause_every", 20)))
        minutes = tk.StringVar(value=str(self.cfg.get(f"{pre}_pause_minutes", 5)))
        frame = ttk.Frame(parent)
        chk = ttk.Checkbutton(frame, text=self.t("pause_every"), variable=en,
                              command=lambda: self._on_pause_change(kind))
        chk.grid(row=0, column=0, sticky="w")
        e1 = ttk.Spinbox(frame, from_=1, to=999, width=5, textvariable=every,
                         command=lambda: self._on_pause_change(kind))
        e1.grid(row=0, column=1, padx=4)
        ttk.Label(frame, text=self.t("pause_videos_for")).grid(row=0, column=2)
        e2 = ttk.Spinbox(frame, from_=1, to=999, width=5, textvariable=minutes,
                         command=lambda: self._on_pause_change(kind))
        e2.grid(row=0, column=3, padx=4)
        ttk.Label(frame, text=self.t("pause_minutes")).grid(row=0, column=4)
        setattr(self, f"{kind}_pause_var", en)
        setattr(self, f"{kind}_pause_every_var", every)
        setattr(self, f"{kind}_pause_min_var", minutes)
        setattr(self, f"{kind}_pause_spins", (e1, e2))
        for e in (e1, e2):
            e.bind("<FocusOut>", lambda ev: self._on_pause_change(kind))
        controls = self._yt_controls if kind == "yt" else self._dl_controls
        controls += [chk, e1, e2]
        self._update_pause_enabled(kind)
        return frame

    def _on_pause_change(self, kind):
        pre = "youtube" if kind == "yt" else "download"

        def _int(var, default):
            try:
                return max(1, int(float(var.get())))
            except (TypeError, ValueError):
                return default
        self.cfg[f"{pre}_pause_enabled"] = bool(getattr(self, f"{kind}_pause_var").get())
        self.cfg[f"{pre}_pause_every"] = _int(getattr(self, f"{kind}_pause_every_var"), 20)
        self.cfg[f"{pre}_pause_minutes"] = _int(getattr(self, f"{kind}_pause_min_var"), 5)
        self._save_config()
        self._update_pause_enabled(kind)

    def _update_pause_enabled(self, kind):
        spins = getattr(self, f"{kind}_pause_spins", None)
        if not spins:
            return
        st = "normal" if getattr(self, f"{kind}_pause_var").get() else "disabled"
        for s in spins:
            try:
                s.configure(state=st)
            except tk.TclError:
                pass

    def _pause_params(self, kind):
        """Return (every_n, pause_seconds) if enabled, else (0, 0)."""
        pre = "youtube" if kind == "yt" else "download"
        if not self.cfg.get(f"{pre}_pause_enabled"):
            return 0, 0
        every = int(self.cfg.get(f"{pre}_pause_every", 20) or 0)
        minutes = int(self.cfg.get(f"{pre}_pause_minutes", 5) or 0)
        if every <= 0 or minutes <= 0:
            return 0, 0
        return every, minutes * 60

    def _enforce_caps(self, count, soft, hard):
        if count > hard:
            messagebox.showerror(self.t("cap_hard_title"),
                                 self.t("cap_hard_msg", n=count, max=hard))
            return False
        if count > soft:
            return self._confirm_dialog(
                self.t("cap_soft_title"), self.t("cap_soft_q", n=count),
                self.t("cap_soft_ok"), self.t("cap_soft_cancel"))
        return True

    def _confirm_dialog(self, title, message, ok_label, cancel_label):
        """Modal yes/no with custom button labels. Returns True if OK chosen."""
        win = tk.Toplevel(self)
        win.title(title)
        win.transient(self)
        win.resizable(False, False)
        result = {"ok": False}
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(frm, text="\u26a0", font=("TkDefaultFont", 20)).pack()
        ttk.Label(frm, text=message, wraplength=420, justify="left"
                  ).pack(pady=(6, 12))
        btns = ttk.Frame(frm)
        btns.pack()

        def choose(ok):
            result["ok"] = ok
            win.destroy()
        ttk.Button(btns, text=ok_label, command=lambda: choose(True)).pack(side="left", padx=6)
        ttk.Button(btns, text=cancel_label, command=lambda: choose(False)).pack(side="left", padx=6)
        win.bind("<Escape>", lambda e: choose(False))
        win.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        win.update_idletasks()
        try:
            win.grab_set()
        except tk.TclError:
            pass
        self.wait_window(win)
        return result["ok"]

    def _get_speed_factor(self, model):
        """Returns (factor, is_confident). is_confident=False means no real
        sample exists yet for this model and the conservative default is
        being used."""
        history = getattr(self, "_eta_history", None)
        if history is None:
            history = load_eta_history()
            self._eta_history = history
        entry = history.get(model) if isinstance(history, dict) else None
        if isinstance(entry, dict) and entry.get("avg", 0) > 0:
            return float(entry["avg"]), True
        return DEFAULT_SPEED_FACTOR, False

    def _set_speed_factor(self, model, sample):
        if not model:
            return
        history = getattr(self, "_eta_history", None)
        if history is None:
            history = load_eta_history()
        entry = history.get(model) if isinstance(history, dict) else None
        history[model] = update_speed_factor_rolling(entry, sample)
        self._eta_history = history
        save_eta_history(history)

    # ---- shared link ingest (single videos + playlist expansion) ---------
    def _ingest_links(self, raw, items_list, target):
        existing = {getattr(it, "video_id", None) for it in items_list}
        added = invalid = playlists = 0
        new_singles = []
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        live_q = (getattr(self, "dl_live_queue", None)
                 if (target == "download" and self.download_is_running) else None)
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            vid = youtube_video_id(line)
            if vid:
                if vid in existing:
                    continue
                item = QueueItem(line)
                item.filename = line
                item.video_id = vid
                if live_q is not None:
                    live_q.add(item)
                else:
                    items_list.append(item)
                existing.add(vid)
                new_singles.append(item)
                added += 1
                continue
            plist = youtube_playlist_id(line)
            if plist:
                if is_mix_playlist(plist):
                    self._append_text(log_widget, self.t("yt_playlist_mix_rejected") + "\n")
                    invalid += 1
                    continue
                if not self.ytdlp_ok:
                    messagebox.showwarning(self.t("warn"),
                                           self.t("yt_need_ytdlp_playlist"))
                    invalid += 1
                    continue
                self._expand_playlist_async(line, target)
                playlists += 1
                continue
            invalid += 1
        if new_singles:
            self._probe_youtube_lengths(new_singles, target)
        return added, invalid, playlists

    def _expand_playlist_async(self, url, target):
        ev_queue = self.youtube_event_queue if target == "youtube" else self.download_event_queue
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        self._append_text(log_widget, self.t("yt_log_fetching_playlist"))
        prefix = ytdlp_command_prefix(self.python_exe)
        worker = PlaylistExpandWorker(prefix, url, self.s, ev_queue, threading.Event())
        worker._target = target
        self._expand_workers.append(worker)
        worker.start()

    def _apply_expanded_entries(self, entries, target):
        items_list = self.youtube_queue_items if target == "youtube" else self.download_queue_items
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        existing = {getattr(it, "video_id", None) for it in items_list}
        added = 0
        new_items = []
        live_q = (getattr(self, "dl_live_queue", None)
                 if (target == "download" and self.download_is_running) else None)
        for e in entries:
            vid = e.get("id")
            if not vid or vid in existing:
                continue
            url = f"https://www.youtube.com/watch?v={vid}"
            item = QueueItem(url)
            item.video_id = vid
            # flat-playlist titles are often locale-translated; treat as a
            # placeholder and let the per-video probe set the ORIGINAL title.
            item.title = e.get("title")
            item.filename = e.get("title") or url
            d = e.get("duration")
            item.duration = float(d) if isinstance(d, (int, float)) and d else None
            if live_q is not None:
                live_q.add(item)
            else:
                items_list.append(item)
            existing.add(vid)
            new_items.append(item)
            added += 1
        if not entries:
            self._append_text(log_widget, self.t("yt_playlist_empty") + "\n")
        else:
            self._append_text(log_widget, self.t("yt_playlist_added", n=added) + "\n")
        if target == "youtube":
            self._render_youtube_queue()
            self._update_youtube_summary()
        else:
            self._render_download_queue()
            self._update_download_summary()
        if new_items:
            # fetch original-language titles + accurate length/date in background
            self._probe_youtube_lengths(new_items, target)

    # ---- async length probing -------------------------------------------
    def _probe_media_lengths(self, items):
        if not self.ffmpeg_path:
            return
        ffmpeg = self.ffmpeg_path

        def work():
            for it in items:
                try:
                    dur = ffmpeg_probe_duration(ffmpeg, it.filepath)
                except Exception:
                    dur = None
                self._probe_event_queue.put(
                    {"target": "trans", "item": it, "duration": dur})
        th = threading.Thread(target=work, daemon=True)
        self._probe_threads.append(th)
        th.start()

    def _probe_youtube_lengths(self, items, target):
        prefix = ytdlp_command_prefix(self.python_exe) if self.ytdlp_ok else None

        def work():
            for it in items:
                vid = getattr(it, "video_id", None)
                if not vid:
                    continue
                try:
                    meta = youtube_metadata(vid, prefix=prefix)
                except Exception:
                    meta = None
                if meta:
                    self._probe_event_queue.put(
                        {"target": target, "item": it,
                         "duration": meta.get("duration"),
                         "title": meta.get("title"),
                         "upload_date": meta.get("upload_date")})
        th = threading.Thread(target=work, daemon=True)
        self._probe_threads.append(th)
        th.start()

    def _poll_probe_events(self):
        try:
            while True:
                ev = self._probe_event_queue.get_nowait()
                self._handle_probe_event(ev)
        except queue.Empty:
            pass
        self.after(150, self._poll_probe_events)

    def _handle_probe_event(self, ev):
        it = ev.get("item")
        if it is None:
            return
        d = ev.get("duration")
        if isinstance(d, (int, float)) and d and d > 0:
            it.duration = float(d)
        title = ev.get("title")
        if title:
            # full per-video extraction returns the ORIGINAL-language title;
            # overwrite the (possibly translated) flat-playlist placeholder.
            it.title = title
            it.filename = title
        if ev.get("upload_date"):
            it.upload_date = ev.get("upload_date")
            it.meta_fetched = True
        target = ev.get("target")
        if target == "trans":
            self._render_queue()
            self._update_trans_summary()
        elif target == "youtube":
            self._render_youtube_queue()
            self._update_youtube_summary()
        elif target == "download":
            self._render_download_queue()
            self._update_download_summary()

    # ---- summary lines ---------------------------------------------------
    def _update_trans_summary(self):
        if not hasattr(self, "trans_summary_var"):
            return
        total, n_known, secs = queue_length_summary(self.queue_items)
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        elif total:
            parts.append(self.t("summary_unknown_hint"))
        self.trans_summary_var.set("   ·   ".join(parts))

    def _update_md_summary(self):
        if not hasattr(self, "md_summary_var"):
            return
        items = self.md_queue_items
        total = len(items)
        size = sum((it.size_bytes or 0) for it in items)
        per = float(self.cfg.get("md_per_file_seconds", MD_PER_FILE_DEFAULT))
        parts = [self.t("summary_files", n=total),
                 self.t("summary_total_size", size=self._human_bytes(size) if size else "—")]
        if total:
            parts.append(self.t("summary_est_convert",
                                eta="≈ " + fmt_long_duration(total * per)))
        self.md_summary_var.set("   ·   ".join(parts))

    def _update_youtube_summary(self):
        if not hasattr(self, "yt_summary_var"):
            return
        items = self.youtube_queue_items
        total, n_known, secs = queue_length_summary(items)
        per = float(self.cfg.get("yt_per_video_seconds", YT_PER_VIDEO_DEFAULT))
        delay = sum(YT_TRANSCRIBE_DELAY) / 2.0
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        if total:
            eta = total * (per + delay)
            parts.append(self.t("summary_est_transcribe", eta="≈ " + fmt_long_duration(eta)))
        self.yt_summary_var.set("   ·   ".join(parts))

    def _update_download_summary(self):
        if not hasattr(self, "dl_summary_var"):
            return
        items = self.download_queue_items
        total, n_known, secs = queue_length_summary(items)
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        elif total:
            parts.append(self.t("summary_unknown_hint"))
        if getattr(self, "dl_transcribe_var", None) and self.dl_transcribe_var.get():
            parts.append(self.t("dl_summary_transcribe_note"))
        self.dl_summary_var.set("   ·   ".join(parts))

    # ======================================================================
    # yt-dlp settings dialog
    # ======================================================================
    def _open_ytdlp_settings(self):
        win = tk.Toplevel(self)
        win.title(self.t("set_ytdlp_title"))
        win.transient(self)
        win.geometry("560x360")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        ttk.Label(frm, text=self.t("set_ytdlp_about"), wraplength=520,
                  foreground="#555").grid(row=0, column=0, sticky="w", pady=(0, 8))
        status_var = tk.StringVar()
        status_lbl = ttk.Label(frm, textvariable=status_var,
                               font=("TkDefaultFont", 10, "bold"))
        status_lbl.grid(row=1, column=0, sticky="w", pady=(0, 8))

        log = tk.Text(frm, height=8, wrap="word", state="disabled",
                      font=("TkFixedFont", 9))
        log.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        frm.rowconfigure(2, weight=1)

        def refresh_status():
            self.ytdlp_ok = ytdlp_is_available(self.python_exe)
            if self.ytdlp_ok:
                status_var.set(self.t("set_ytdlp_found"))
                status_lbl.configure(foreground="#1a7f37")
            else:
                status_var.set(self.t("set_ytdlp_missing"))
                status_lbl.configure(foreground="#cf222e")
            self._refresh_youtube_enabled()
            self._refresh_download_enabled()

        def do_install():
            cmd = build_pip_install_command(self.python_exe, "yt-dlp")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_ytdlp_install_q",
                                              cmd=" ".join(cmd)), parent=win):
                return
            self._append_text(log, self.t("install_running"))
            install_btn.configure(state="disabled")
            recheck_btn.configure(state="disabled")
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="ytdlp")
            worker.start()

            def done(success, error):
                install_btn.configure(state="normal")
                recheck_btn.configure(state="normal")
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
            self._attach_stream(q, log, done)

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="ew")
        install_btn = ttk.Button(btns, text=self.t("set_ytdlp_install"),
                                 command=do_install)
        install_btn.pack(side="left", padx=2)
        recheck_btn = ttk.Button(btns, text=self.t("set_recheck"),
                                 command=refresh_status)
        recheck_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("close"),
                   command=win.destroy).pack(side="right", padx=2)
        refresh_status()

    # ======================================================================
    # Download tab
    # ======================================================================
    def _build_download_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)   # queue expands
        self._dl_controls = []

        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(3, weight=1)
        self.dl_ind_ytdlp = tk.Label(status, text="", cursor="hand2",
                                     font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ytdlp.grid(row=0, column=0, padx=8, pady=6)
        self.dl_ind_ytdlp.bind("<Button-1>", lambda e: self._open_ytdlp_settings())
        self.dl_ind_ffmpeg = tk.Label(status, text="", cursor="hand2",
                                      font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ffmpeg.grid(row=0, column=1, padx=8, pady=6)
        self.dl_ind_ffmpeg.bind("<Button-1>", lambda e: self._open_ffmpeg_settings())
        self.dl_ind_whisper = tk.Label(status, text="", cursor="hand2",
                                       font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_whisper.grid(row=0, column=2, padx=8, pady=6)
        self.dl_ind_whisper.bind("<Button-1>", lambda e: self._open_whisper_settings())
        ttk.Label(status, text=self.t("dep_hint"), foreground="#777"
                  ).grid(row=0, column=3, sticky="e", padx=8)

        intro = ttk.Label(root, text=self.t("dl_intro"), foreground="#555")
        intro.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 0))
        intro.configure(wraplength=900)

        # options
        opt = ttk.LabelFrame(root, text=self.t("dl_options"))
        opt.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        for c in range(6):
            opt.columnconfigure(c, weight=0)
        self.dl_audio_only_var = tk.BooleanVar(value=bool(self.cfg.get("download_audio_only", False)))
        ck = ttk.Checkbutton(opt, text=self.t("dl_audio_only"),
                             variable=self.dl_audio_only_var, command=self._on_dl_opts_change)
        ck.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self._dl_controls.append(ck)
        ttk.Label(opt, text=self.t("dl_resolution")).grid(row=0, column=1, sticky="e", padx=4)
        self.dl_res_var = tk.StringVar(value=self.cfg.get("download_resolution", "best"))
        self.dl_res_combo = ttk.Combobox(opt, textvariable=self.dl_res_var, state="readonly",
                                         width=8, values=[self.t("dl_res_best")] +
                                         [r for r in DOWNLOAD_RESOLUTIONS if r != "best"])
        self._sync_res_combo_display()
        self.dl_res_combo.grid(row=0, column=2, sticky="w", padx=4)
        self.dl_res_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_res_combo)
        ttk.Label(opt, text=self.t("dl_audio_format")).grid(row=0, column=3, sticky="e", padx=4)
        self.dl_audiofmt_var = tk.StringVar(value=self.cfg.get("download_audio_format", "mp3"))
        self.dl_audiofmt_combo = ttk.Combobox(opt, textvariable=self.dl_audiofmt_var,
                                              state="readonly", width=7,
                                              values=DOWNLOAD_AUDIO_FORMATS)
        self.dl_audiofmt_combo.grid(row=0, column=4, sticky="w", padx=4)
        self.dl_audiofmt_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_audiofmt_combo)
        ttk.Label(opt, text=self.t("dl_container")).grid(row=0, column=5, sticky="e", padx=4)
        self.dl_container_var = tk.StringVar(value=self.cfg.get("download_container", "mp4"))
        self.dl_container_combo = ttk.Combobox(opt, textvariable=self.dl_container_var,
                                              state="readonly", width=6,
                                              values=DOWNLOAD_CONTAINERS)
        self.dl_container_combo.grid(row=0, column=6, sticky="w", padx=4)
        self.dl_container_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_container_combo)
        self.dl_ffmpeg_note = ttk.Label(opt, text=self.t("dl_ffmpeg_note"), foreground="#777")
        self.dl_ffmpeg_note.grid(row=1, column=0, columnspan=7, sticky="w", padx=6, pady=(0, 4))

        # output dir (single fixed folder)
        of = ttk.LabelFrame(root, text=self.t("fixed_folder"))
        of.grid(row=3, column=0, sticky="ew", padx=8, pady=2)
        of.columnconfigure(0, weight=1)
        self.dl_outdir_var = tk.StringVar(value=self.cfg.get("download_output_dir", ""))
        dl_entry = ttk.Entry(of, textvariable=self.dl_outdir_var)
        dl_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        b_br = ttk.Button(of, text=self.t("browse"), command=self._dl_browse_outdir)
        b_br.grid(row=0, column=1, padx=6, pady=6)
        self._dl_controls += [dl_entry, b_br]

        # queue
        qf = ttk.LabelFrame(root, text=self.t("dl_queue_frame"))
        qf.grid(row=4, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        qbtns = ttk.Frame(qf)
        qbtns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        b_add = ttk.Button(qbtns, text=self.t("btn_add"),
                           command=lambda: self._open_add_links_dialog("download"))
        b_add.pack(side="left", padx=2)
        b_rm = ttk.Button(qbtns, text=self.t("remove_selected"), command=self._dl_remove_selected)
        b_rm.pack(side="left", padx=2)
        b_cl = ttk.Button(qbtns, text=self.t("clear_queue"), command=self._dl_clear_queue)
        b_cl.pack(side="left", padx=2)
        self.dl_clear_queue_btn = b_cl
        b_up = ttk.Button(qbtns, text=self.t("move_up"),
                          command=lambda: self._dl_move_selected(-1))
        b_up.pack(side="left", padx=2)
        b_dn = ttk.Button(qbtns, text=self.t("move_down"),
                          command=lambda: self._dl_move_selected(1))
        b_dn.pack(side="left", padx=2)
        self._dl_controls += [b_add, b_rm, b_cl, b_up, b_dn]
        cols = ("order", "video", "length", "status")
        qwrap, self.dl_tree, _dsb = make_scrollable_queue(qf, cols, height=13)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.dl_tree.heading("order", text=self.t("col_order"))
        self.dl_tree.heading("video", text=self.t("yt_col_video"))
        self.dl_tree.heading("length", text=self.t("col_length"))
        self.dl_tree.heading("status", text=self.t("col_status"))
        self.dl_tree.column("order", width=40, anchor="center", stretch=False)
        self.dl_tree.column("video", width=460)
        self.dl_tree.column("length", width=90, anchor="center", stretch=False)
        self.dl_tree.column("status", width=160, anchor="center")
        self.dl_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.dl_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # transcribe-after-download + Whisper settings
        trow = ttk.Frame(root)
        trow.grid(row=5, column=0, sticky="ew", padx=10, pady=2)
        self.dl_transcribe_var = tk.BooleanVar(value=bool(self.cfg.get("download_transcribe", False)))
        tchk = ttk.Checkbutton(trow, text=self.t("dl_transcribe_after"),
                               variable=self.dl_transcribe_var,
                               command=self._on_dl_transcribe_toggle)
        tchk.grid(row=0, column=0, sticky="w")
        self.dl_whisper_btn = ttk.Button(trow, text=self.t("dl_define_whisper"),
                                         command=self._open_dl_whisper_settings)
        self.dl_whisper_btn.grid(row=0, column=1, padx=10)
        self._dl_controls += [tchk, self.dl_whisper_btn]

        # pause control
        self._build_pause_box(root, "dl").grid(row=6, column=0, sticky="ew", padx=8, pady=2)

        # run controls
        rf = ttk.Frame(root)
        rf.grid(row=7, column=0, sticky="ew", padx=8, pady=4)
        rf.columnconfigure(2, weight=1)
        self.dl_start_btn = ttk.Button(rf, text=self.t("dl_start"), command=self._start_download_batch)
        self.dl_start_btn.grid(row=0, column=0, padx=2)
        self.dl_cancel_btn = ttk.Button(rf, text=self.t("cancel"),
                                        command=self._cancel_download_batch, state="disabled")
        self.dl_cancel_btn.grid(row=0, column=1, padx=2)
        self.dl_open_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                      command=self._dl_open_output, state="disabled")
        self.dl_open_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.dl_progress = TwoToneProgress(rf, height=22)
        self.dl_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.dl_progress_pct_var = tk.StringVar(value="")
        self.dl_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.dl_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log
        logf = ttk.LabelFrame(root, text=self.t("dl_log_frame"))
        logf.grid(row=8, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.dl_log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        dsb = ttk.Scrollbar(logf, orient="vertical", command=self.dl_log_text.yview)
        self.dl_log_text.configure(yscrollcommand=dsb.set)
        self.dl_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        dsb.grid(row=0, column=1, sticky="ns", pady=4)
        self._on_dl_transcribe_toggle()

    def _sync_res_combo_display(self):
        cur = self.cfg.get("download_resolution", "best")
        self.dl_res_var.set(self.t("dl_res_best") if cur == "best" else cur)

    def _on_dl_opts_change(self):
        disp = self.dl_res_var.get()
        res = "best" if disp == self.t("dl_res_best") else disp
        if res not in DOWNLOAD_RESOLUTIONS:
            res = "best"
        self.cfg["download_resolution"] = res
        self.cfg["download_audio_only"] = bool(self.dl_audio_only_var.get())
        af = self.dl_audiofmt_var.get()
        self.cfg["download_audio_format"] = af if af in DOWNLOAD_AUDIO_FORMATS else "mp3"
        cn = self.dl_container_var.get()
        self.cfg["download_container"] = cn if cn in DOWNLOAD_CONTAINERS else "mp4"
        self._save_config()
        # audio-only disables resolution + container; enables audio format
        if self.dl_audio_only_var.get():
            self.dl_res_combo.configure(state="disabled")
            self.dl_container_combo.configure(state="disabled")
            self.dl_audiofmt_combo.configure(state="readonly")
        else:
            self.dl_res_combo.configure(state="readonly")
            self.dl_container_combo.configure(state="readonly")
            self.dl_audiofmt_combo.configure(state="disabled")

    def _refresh_download_enabled(self):
        if not hasattr(self, "dl_ind_ytdlp"):
            return
        yok = bool(getattr(self, "ytdlp_ok", False))
        ymark = self.t("dep_found") if yok else self.t("dep_missing")
        self.dl_ind_ytdlp.configure(text=f"{self.t('dep_ytdlp')} {ymark}",
                                    fg=("#1a7f37" if yok else "#cf222e"))
        fok = bool(self.ffmpeg_path)
        fmark = self.t("dep_found") if fok else self.t("dep_missing")
        self.dl_ind_ffmpeg.configure(text=f"{self.t('dep_ffmpeg')} {fmark}",
                                     fg=("#1a7f37" if fok else "#cf222e"))
        if hasattr(self, "dl_ind_whisper"):
            wok = bool(self.whisper_path)
            wmark = self.t("dep_found") if wok else self.t("dep_missing")
            self.dl_ind_whisper.configure(text=f"{self.t('dep_whisper')} {wmark}",
                                          fg=("#1a7f37" if wok else "#cf222e"))
        state = "normal" if (yok and not self.download_is_running) else "disabled"
        if hasattr(self, "dl_start_btn"):
            self.dl_start_btn.configure(state=state)
        if hasattr(self, "dl_whisper_btn") and not self.download_is_running:
            self.dl_whisper_btn.configure(
                state=("normal" if self.dl_transcribe_var.get() else "disabled"))
        # reflect audio-only toggle on first build
        if hasattr(self, "dl_res_combo"):
            self._on_dl_opts_change()

    def _on_dl_transcribe_toggle(self):
        on = bool(self.dl_transcribe_var.get())
        self.cfg["download_transcribe"] = on
        self._save_config()
        if hasattr(self, "dl_whisper_btn") and not self.download_is_running:
            self.dl_whisper_btn.configure(state=("normal" if on else "disabled"))
        self._update_download_summary()

    def _dictionary_payload(self, name):
        if not name or name == self.t("none"):
            return "", []
        prof = self.dictionaries.get(name, {})
        return (prof.get("initial_prompt") or prof.get("prompt") or ""), \
            prof.get("replacements", [])

    def _open_dl_whisper_settings(self):
        """Pick the model + audio language + vocabulary dictionary to use for
        transcribing downloaded videos. Mirrors the A/V tab's controls."""
        win = tk.Toplevel(self)
        win.title(self.t("dl_define_whisper"))
        win.transient(self)
        win.resizable(False, False)
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=14, pady=14)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("dl_whisper_intro"), foreground="#555",
                  wraplength=460, justify="left").grid(row=0, column=0, columnspan=2,
                                                       sticky="w", pady=(0, 10))
        # audio language
        codes = self.cfg.get("audio_langs", list(DEFAULT_AUDIO_LANGS))
        lang_disp = [self._audio_lang_display(c) for c in codes]
        code_by_disp = dict(zip(lang_disp, codes))
        ttk.Label(frm, text=self.t("audio_language")).grid(row=1, column=0, sticky="w", pady=4)
        lang_var = tk.StringVar()
        lang_combo = ttk.Combobox(frm, textvariable=lang_var, state="readonly",
                                  width=28, values=lang_disp)
        lang_combo.grid(row=1, column=1, sticky="ew", pady=4)
        cur_lang = self.cfg.get("download_whisper_lang") or self.cfg.get("audio_lang_code", "pt")
        if cur_lang not in codes:
            cur_lang = codes[0] if codes else "pt"
        lang_combo.set(self._audio_lang_display(cur_lang))
        # model (filtered by language, installed only)
        ttk.Label(frm, text=self.t("ai_model")).grid(row=2, column=0, sticky="w", pady=4)
        model_var = tk.StringVar()
        model_combo = ttk.Combobox(frm, textvariable=model_var, state="readonly", width=34)
        model_combo.grid(row=2, column=1, sticky="ew", pady=4)
        model_status = ttk.Label(frm, text="", foreground="#555")
        model_status.grid(row=3, column=1, sticky="w")
        model_cli_by_disp = {}

        def refill_models():
            nonlocal model_cli_by_disp
            code = code_by_disp.get(lang_var.get(), cur_lang)
            installed = models_for_audio_language(code, only_installed=True)
            disp = [self._model_display(c) for c in installed]
            model_cli_by_disp = dict(zip(disp, installed))
            model_combo["values"] = disp
            want = self.cfg.get("download_whisper_model") or self.cfg.get("model_cli", "")
            if installed:
                model_combo.set(self._model_display(want if want in installed else installed[0]))
                model_status.configure(text="")
            else:
                model_combo.set("")
                model_status.configure(text=self.t("no_models_installed"))
        refill_models()
        lang_combo.bind("<<ComboboxSelected>>", lambda e: refill_models())
        # dictionary
        ttk.Label(frm, text=self.t("vocab_dict")).grid(row=4, column=0, sticky="w", pady=4)
        dict_var = tk.StringVar()
        dict_names = [self.t("none")] + sorted(self.dictionaries.keys())
        dict_combo = ttk.Combobox(frm, textvariable=dict_var, state="readonly",
                                  width=34, values=dict_names)
        dict_combo.grid(row=4, column=1, sticky="ew", pady=4)
        cur_dict = self.cfg.get("download_whisper_dictionary", "")
        dict_combo.set(cur_dict if cur_dict in self.dictionaries else self.t("none"))
        ttk.Button(frm, text=self.t("add_model") + " / " + self.t("add_languages"),
                   command=lambda: self._open_whisper_settings()).grid(
                       row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))

        def save_and_close():
            code = code_by_disp.get(lang_var.get(), cur_lang)
            self.cfg["download_whisper_lang"] = code
            self.cfg["download_whisper_model"] = model_cli_by_disp.get(model_var.get(), "")
            dn = dict_var.get()
            self.cfg["download_whisper_dictionary"] = "" if dn == self.t("none") else dn
            self._save_config()
            win.destroy()
        ttk.Button(btns, text=self.t("save"), command=save_and_close).pack(side="left", padx=4)
        ttk.Button(btns, text=self.t("cancel"), command=win.destroy).pack(side="left", padx=4)
        win.update_idletasks()
        try:
            win.grab_set()
        except tk.TclError:
            pass

    # ---- download queue ops ----
    def _dl_move_selected(self, direction):
        sel = self.dl_tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        if self.download_is_running and getattr(self, "dl_live_queue", None) is not None:
            moved = self.dl_live_queue.move(moving_id, direction)
            if not moved:
                target = next((it for it in self.download_queue_items
                              if it.item_id == moving_id), None)
                if target is not None and target.status != ST_PENDING:
                    messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))
                return
            self._render_download_queue()
            self.dl_tree.selection_set(str(moving_id))
            return
        by_id = {it.item_id: i for i, it in enumerate(self.download_queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if not (0 <= new < len(self.download_queue_items)):
            return
        self.download_queue_items[idx], self.download_queue_items[new] = \
            self.download_queue_items[new], self.download_queue_items[idx]
        self._render_download_queue()

    def _dl_remove_selected(self):
        locked_selected = False
        ids_to_remove = []
        by_id = {it.item_id: it for it in self.download_queue_items}
        for iid in self.dl_tree.selection():
            it = by_id.get(int(iid))
            if it is None:
                continue
            if it.status != ST_PENDING:
                locked_selected = True
                continue
            ids_to_remove.append(it.item_id)
        for item_id in ids_to_remove:
            if self.download_is_running and getattr(self, "dl_live_queue", None) is not None:
                self.dl_live_queue.remove(item_id)
            else:
                self.download_queue_items = [it for it in self.download_queue_items
                                             if it.item_id != item_id]
        if ids_to_remove:
            self._render_download_queue()
            self._update_download_summary()
        if locked_selected:
            messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))

    def _dl_clear_queue(self):
        if self.download_is_running:
            # Button is disabled while running; this is a defensive fallback.
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.download_queue_items = []
        self._render_download_queue()
        self._update_download_summary()

    def _dl_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_dl"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_download_queue(self):
        if not hasattr(self, "dl_tree"):
            return
        self.dl_tree.delete(*self.dl_tree.get_children())
        for i, it in enumerate(self.download_queue_items):
            label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                else self._dl_status_text(it.status)
            length = fmt_hms(it.duration) if it.duration else "…"
            self.dl_tree.insert("", "end", iid=str(it.item_id),
                                values=(i + 1, it.filename, length, label))

    def _dl_browse_outdir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.dl_outdir_var.set(d)
            self.cfg["download_output_dir"] = d
            self._save_config()

    def _dl_open_output(self):
        for it in self.download_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return
        if self.dl_outdir_var.get():
            self._open_path(self.dl_outdir_var.get())

    # ---- download run ----
    def _start_download_batch(self):
        if self.download_is_running:
            return
        if not self.ytdlp_ok:
            messagebox.showerror(self.t("error"), self.t("dl_need_ytdlp"))
            self._open_ytdlp_settings()
            return
        if not self.download_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self._enforce_caps(len(self.download_queue_items),
                                  DOWNLOAD_SOFT_CAP, DOWNLOAD_HARD_CAP):
            return
        out_dir = self.dl_outdir_var.get().strip()
        if not out_dir:
            messagebox.showerror(self.t("error"), self.t("dl_need_output_dir"))
            return
        progressive = False
        if not self.ffmpeg_path:
            if not messagebox.askyesno(self.t("warn"), self.t("dl_ffmpeg_nudge_q")):
                return
            progressive = True

        # transcribe-after-download gating
        transcribe = bool(self.dl_transcribe_var.get())
        w_model = w_lang_param = w_prompt = ""
        w_reps = []
        w_formats = []
        if transcribe:
            if not self.whisper_path:
                messagebox.showerror(self.t("error"), self.t("dl_need_whisper"))
                self._open_whisper_settings()
                return
            if not self.ffmpeg_path:
                messagebox.showerror(self.t("error"), self.t("dl_transcribe_needs_ffmpeg"))
                return
            w_model = self.cfg.get("download_whisper_model", "")
            w_lang = self.cfg.get("download_whisper_lang", "")
            installed = models_for_audio_language(w_lang or "pt", only_installed=True)
            if not w_model or not w_lang or w_model not in installed:
                messagebox.showerror(self.t("error"), self.t("dl_whisper_not_defined"))
                self._open_dl_whisper_settings()
                return
            w_formats = self._selected_keep_formats()
            if not w_formats:
                messagebox.showerror(self.t("error"), self.t("err_no_format"))
                self._open_output_formats()
                return
            w_lang_param = audio_lang_param(w_lang)
            w_prompt, w_reps = self._dictionary_payload(
                self.cfg.get("download_whisper_dictionary", ""))

        self.cfg["download_output_dir"] = out_dir
        self._save_config()
        for it in self.download_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_download_queue()
        audio_only = bool(self.dl_audio_only_var.get())
        res = self.cfg.get("download_resolution", "best")
        prefix = ytdlp_command_prefix(self.python_exe)
        every, pause_seconds = self._pause_params("dl")
        self.download_stop_flag = threading.Event()
        self.dl_live_queue = LiveQueue(self.download_queue_items)
        self.download_worker = DownloadWorker(
            items=self.dl_live_queue, prefix=prefix, out_dir=out_dir,
            audio_only=audio_only, audio_format=self.cfg.get("download_audio_format", "mp3"),
            resolution=res, container=self.cfg.get("download_container", "mp4"),
            ffmpeg_location=self.ffmpeg_path, strings=self.s,
            event_queue=self.download_event_queue, stop_flag=self.download_stop_flag,
            delay_range=YT_DOWNLOAD_DELAY, progressive=progressive,
            pause_every=every, pause_seconds=pause_seconds,
            transcribe=transcribe, whisper_exe=self.whisper_path,
            whisper_model=w_model, whisper_lang_param=w_lang_param,
            whisper_task="transcribe", whisper_prompt=w_prompt,
            whisper_replacements=w_reps, whisper_formats=w_formats)
        self.download_is_running = True
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_cur_running_id = None
        self.dl_start_btn.configure(state="disabled")
        self.dl_cancel_btn.configure(state="normal")
        self.dl_open_btn.configure(state="disabled")
        if hasattr(self, "dl_clear_queue_btn"):
            self.dl_clear_queue_btn.configure(state="disabled")
        self._clear_log(self.dl_log_text)
        self._append_text(self.dl_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self._set_progress(self.dl_progress, self.dl_progress_pct_var, 0.0)
        self.download_worker.start()

    def _cancel_download_batch(self):
        if self.download_is_running and self.download_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.dl_log_text, self.t("log_canceling"))
                self.download_worker.cancel()

    def _poll_download_events(self):
        try:
            while True:
                ev = self.download_event_queue.get_nowait()
                self._handle_download_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_download_events)

    def _handle_download_event(self, ev):
        kind = ev.get("kind")
        if kind == "dl_log":
            self._append_text(self.dl_log_text, ev.get("text", ""))
        elif kind == "expand_done":
            self._apply_expanded_entries(ev.get("entries", []), "download")
        elif kind == "expand_error":
            short, _ = youtube_error_message(ev.get("cause", "generic"), self.s,
                                             raw=ev.get("raw", ""))
            self._append_text(self.dl_log_text,
                              self.t("yt_expand_error", e=short) + "\n")
        elif kind == "dl_progress":
            pct = ev.get("percent")
            if pct is not None:
                self._set_progress(self.dl_progress, self.dl_progress_pct_var, pct)
        elif kind == "dl_progress_item":
            self._dl_cur_running_id = ev.get("item_id")
            self._update_dl_progress_label()
        elif kind == "dl_item_status":
            item_id = ev.get("item_id")
            status = ev.get("status")
            it = next((q for q in self.download_queue_items if q.item_id == item_id), None)
            if it is not None:
                it.status = status
                if ev.get("error"):
                    it.error_message = ev["error"]
                try:
                    self.dl_tree.set(str(item_id), "status",
                                     ev.get("error") or self._dl_status_text(status))
                except tk.TclError:
                    pass
            if status in ST_TERMINAL:
                if status == ST_DONE:
                    self._dl_done += 1
                elif status == ST_ERROR:
                    self._dl_errors += 1
                self._update_dl_progress_label()
        elif kind == "dl_substatus":
            item_id = ev.get("item_id")
            try:
                self.dl_tree.set(str(item_id), "status", ev.get("text", ""))
            except tk.TclError:
                pass
        elif kind == "dl_batch_blocked":
            messagebox.showwarning(self.t("yt_block_title"),
                                   ev.get("message") or self.t("yt_block_dialog"))
        elif kind == "dl_batch_finished":
            self._on_download_batch_finished()

    def _update_dl_progress_label(self):
        total = max(1, len(self.download_queue_items))
        done = self._dl_done + self._dl_errors
        cur = current_processing_index(done, total, self.download_is_running)
        self.dl_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_download_batch_finished(self):
        self.download_is_running = False
        self.download_worker = None
        self.dl_live_queue = None
        self._set_progress(self.dl_progress, self.dl_progress_pct_var, 100.0)
        self.dl_start_btn.configure(state="normal" if self.ytdlp_ok else "disabled")
        self.dl_cancel_btn.configure(state="disabled")
        self.dl_open_btn.configure(state="normal")
        if hasattr(self, "dl_clear_queue_btn"):
            self.dl_clear_queue_btn.configure(state="normal")
        self._append_text(self.dl_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.dl_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._dl_done, errors=self._dl_errors))
        if self._dl_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._dl_done, errors=self._dl_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._dl_done))

    # ---- grabber tab -----------------------------------------------------
    def _build_grabber_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        intro = ttk.Label(root, text=self.t("grab_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        intro.configure(wraplength=900)

        inf = ttk.LabelFrame(root, text=self.t("grab_input_label"))
        inf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        inf.columnconfigure(0, weight=1)
        self.grab_input = tk.Text(inf, height=4, wrap="none", font=("TkFixedFont", 9))
        self.grab_input.grid(row=0, column=0, sticky="ew", padx=(6, 0), pady=6)
        gisb = ttk.Scrollbar(inf, orient="vertical", command=self.grab_input.yview)
        self.grab_input.configure(yscrollcommand=gisb.set)
        gisb.grid(row=0, column=1, sticky="ns", pady=6)
        btns = ttk.Frame(inf)
        btns.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        self.grab_btn = ttk.Button(btns, text=self.t("grab_btn"), command=self._grab_start)
        self.grab_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("grab_clear"), command=self._grab_clear).pack(side="left", padx=2)
        self.grab_note = ttk.Label(inf, text="", foreground="#cf222e", wraplength=900)
        self.grab_note.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

        modef = ttk.Frame(root)
        modef.grid(row=2, column=0, sticky="ew", padx=10, pady=2)
        self.grab_mode_var = tk.StringVar(value=self.cfg.get("grabber_output_mode", "title_link"))
        ttk.Radiobutton(modef, text=self.t("grab_mode_title_link"), value="title_link",
                        variable=self.grab_mode_var, command=self._on_grab_mode_change
                        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(modef, text=self.t("grab_mode_link_only"), value="link_only",
                        variable=self.grab_mode_var, command=self._on_grab_mode_change
                        ).pack(side="left")

        outf = ttk.LabelFrame(root, text=self.t("grab_output_label"))
        outf.grid(row=4, column=0, sticky="nsew", padx=8, pady=4)
        outf.columnconfigure(0, weight=1)
        outf.rowconfigure(0, weight=1)
        self.grab_output = tk.Text(outf, height=14, wrap="none", font=("TkFixedFont", 9))
        self.grab_output.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        gosb = ttk.Scrollbar(outf, orient="vertical", command=self.grab_output.yview)
        self.grab_output.configure(yscrollcommand=gosb.set)
        gosb.grid(row=0, column=1, sticky="ns", pady=6)
        obtns = ttk.Frame(outf)
        obtns.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        ttk.Button(obtns, text=self.t("grab_copy"), command=self._grab_copy).pack(side="left", padx=2)
        ttk.Button(obtns, text=self.t("grab_save"), command=self._grab_save).pack(side="left", padx=2)
        self.grab_status_var = tk.StringVar(value="")
        ttk.Label(outf, textvariable=self.grab_status_var, foreground="#444"
                  ).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

    def _grab_clear(self):
        self.grab_input.delete("1.0", "end")

    def _format_grab_entries(self, entries):
        mode = self.grab_mode_var.get()
        lines = []
        for e in entries:
            if mode == "link_only":
                lines.append(e["url"])
            else:
                title = (e.get("title") or "").strip() or e["id"]
                lines.append(f"{title} — {e['url']}")
        return "\n".join(lines)

    def _render_grab_output(self):
        self.grab_output.delete("1.0", "end")
        if self._grab_entries:
            self.grab_output.insert("1.0", self._format_grab_entries(self._grab_entries) + "\n")

    def _on_grab_mode_change(self):
        self.cfg["grabber_output_mode"] = self.grab_mode_var.get()
        self._save_config()
        self._render_grab_output()

    def _grab_start(self):
        if self.grabber_is_running:
            return
        if not self.ytdlp_ok:
            self.grab_note.configure(text=self.t("grab_need_ytdlp"))
            return
        self.grab_note.configure(text="")
        raw = self.grab_input.get("1.0", "end").strip()
        urls = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not urls:
            self.grab_note.configure(text=self.t("grab_no_input"))
            return
        self._grab_entries = []
        self.grab_output.delete("1.0", "end")
        self.grab_status_var.set(self.t("grab_working"))
        self.grab_btn.configure(state="disabled")
        self.grabber_is_running = True
        self.grabber_stop_flag = threading.Event()
        prefix = ytdlp_command_prefix(self.python_exe)
        self.grabber_worker = LinkGrabWorker(
            urls, prefix, self.s, self.grabber_event_queue, self.grabber_stop_flag)
        self.grabber_worker.start()

    def _poll_grabber_events(self):
        try:
            while True:
                ev = self.grabber_event_queue.get_nowait()
                self._handle_grabber_event(ev)
        except queue.Empty:
            pass
        self.after(150, self._poll_grabber_events)

    def _handle_grabber_event(self, ev):
        kind = ev.get("kind")
        if kind == "grab_log":
            self.grab_status_var.set(ev.get("text", "").strip())
        elif kind == "grab_done":
            self._grab_entries = ev.get("entries", [])
            self.grabber_is_running = False
            self.grab_btn.configure(state="normal")
            self._render_grab_output()
            if self._grab_entries:
                self.grab_status_var.set(self.t("grab_done_msg", n=len(self._grab_entries)))
            else:
                self.grab_status_var.set(self.t("grab_empty"))
        elif kind == "grab_error":
            self.grabber_is_running = False
            self.grab_btn.configure(state="normal")
            self.grab_status_var.set(self.t("grab_error"))

    def _grab_copy(self):
        text = self.grab_output.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.grab_status_var.set(self.t("grab_copied"))

    def _grab_save(self):
        text = self.grab_output.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            title=self.t("grab_save"), defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            self.grab_status_var.set(self.t("grab_saved", path=path))
        except OSError as e:
            self.grab_status_var.set(str(e))

    # ---- dictionary tab --------------------------------------------------
    def _build_dictionary_tab(self, parent):
        root = ttk.Frame(parent)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(root, text=self.t("saved_profiles"))
        left.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
        self.dict_listbox = tk.Listbox(left, width=26, height=18, exportselection=False)
        self.dict_listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self.dict_listbox.bind("<<ListboxSelect>>", self._on_dict_profile_select)
        lb = ttk.Frame(left)
        lb.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(lb, text=self.t("new"), command=self._dict_new).pack(side="left", padx=2)
        ttk.Button(lb, text=self.t("duplicate"), command=self._dict_duplicate).pack(side="left", padx=2)
        ttk.Button(lb, text=self.t("delete"), command=self._dict_delete).pack(side="left", padx=2)

        right = ttk.LabelFrame(root, text=self.t("edit_profile"))
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        right.rowconfigure(6, weight=1)
        ttk.Label(right, text=self.t("profile_name")).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        self.dict_name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.dict_name_var).grid(row=1, column=0, sticky="ew", padx=6, pady=2)
        ph = ttk.Label(right, text=self.t("priming_help"), foreground="#666", justify="left")
        ph.grid(row=2, column=0, sticky="w", padx=6, pady=(8, 0))
        ph.configure(wraplength=620)
        self.dict_prompt_text = tk.Text(right, height=4, wrap="word")
        self.dict_prompt_text.grid(row=3, column=0, sticky="nsew", padx=6, pady=2)
        rh = ttk.Label(right, text=self.t("replacements_help"), foreground="#666", justify="left")
        rh.grid(row=5, column=0, sticky="w", padx=6, pady=(8, 0))
        rh.configure(wraplength=620)
        self.dict_repl_text = tk.Text(right, height=8, wrap="word")
        self.dict_repl_text.grid(row=6, column=0, sticky="nsew", padx=6, pady=2)
        ttk.Button(right, text=self.t("save_profile"), command=self._dict_save
                   ).grid(row=7, column=0, sticky="e", padx=6, pady=6)
        self._dict_current = None
        self._refresh_dict_listbox()

    # ======================================================================
    # Refresh / state
    # ======================================================================
    def _refresh_status_indicators(self):
        def style(label, name_key, ok):
            mark = self.t("dep_found") if ok else self.t("dep_missing")
            label.configure(text=f"{self.t(name_key)} {mark}",
                            fg=("#1a7f37" if ok else "#cf222e"))
        style(self.ind_whisper, "dep_whisper", bool(self.whisper_path))
        style(self.ind_markitdown, "dep_markitdown", bool(self.markitdown_ok))
        style(self.ind_ffmpeg, "dep_ffmpeg", bool(self.ffmpeg_path))
        self._refresh_youtube_enabled()
        self._refresh_download_enabled()

    def _refresh_audio_lang_dropdown(self):
        codes = self.cfg.get("audio_langs", list(DEFAULT_AUDIO_LANGS))
        displays = [self._audio_lang_display(c) for c in codes]
        self._audio_code_by_display = dict(zip(displays, codes))
        self.audio_lang_combo["values"] = displays
        cur = self.cfg.get("audio_lang_code", "pt")
        if cur not in codes:
            cur = codes[0] if codes else "pt"
            self.cfg["audio_lang_code"] = cur
        self.audio_lang_var.set(self._audio_lang_display(cur))

    def _refresh_model_dropdown(self):
        code = self.cfg.get("audio_lang_code", "pt")
        installed = models_for_audio_language(code, only_installed=True)
        displays = [self._model_display(c) for c in installed]
        self._model_cli_by_display = dict(zip(displays, installed))
        self.model_combo["values"] = displays
        cur = self.cfg.get("model_cli", "turbo")
        if cur not in installed:
            cur = installed[0] if installed else cur
            self.cfg["model_cli"] = cur
        if installed:
            self.model_combo.set(self._model_display(cur))
        else:
            self.model_combo.set("")
        self._refresh_model_status_label()

    def _refresh_model_status_label(self):
        installed = models_for_audio_language(
            self.cfg.get("audio_lang_code", "pt"), only_installed=True)
        if not installed:
            self.model_status_var.set(self.t("no_models_installed"))
            return
        cli = self.cfg.get("model_cli", "turbo")
        info = MODEL_INFO.get(cli, MODEL_INFO["turbo"])
        downloaded, _ = is_model_downloaded(cli)
        size = human_size(info["size_mb"])
        if downloaded:
            self.model_status_var.set(self.t("model_status") + " " +
                                      self.t("model_downloaded", size=size, vram=info["vram_gb"]))
        else:
            self.model_status_var.set(self.t("model_status") + " " +
                                      self.t("model_not_downloaded", size=size, vram=info["vram_gb"]))

    def _refresh_dictionary_dropdown(self):
        names = [self.t("none")] + sorted(self.dictionaries.keys())
        self.dict_combo["values"] = names
        sel = self.cfg.get("selected_dictionary", "")
        if sel and sel in self.dictionaries:
            self.dict_var.set(sel)
        else:
            self.dict_var.set(self.t("none"))

    def _update_clip_gate(self):
        has_ffmpeg = bool(self.ffmpeg_path)
        enabled = self.clip_enabled_var.get() and has_ffmpeg
        state = "normal" if (has_ffmpeg) else "disabled"
        try:
            self.clip_check.configure(state="normal" if has_ffmpeg else "disabled")
            entry_state = "normal" if enabled else "disabled"
            self.clip_start_entry.configure(state=entry_state)
            self.clip_end_entry.configure(state=entry_state)
            if not has_ffmpeg:
                self.clip_enabled_var.set(False)
                self.clip_hint_label.configure(text=self.t("clip_needs_ffmpeg"))
            else:
                self.clip_hint_label.configure(text=self.t("clip_hint"))
        except (AttributeError, tk.TclError):
            pass

    # ======================================================================
    # Change handlers
    # ======================================================================
    def _on_audio_lang_change(self, _event=None):
        disp = self.audio_lang_var.get()
        code = getattr(self, "_audio_code_by_display", {}).get(disp)
        if code:
            self.cfg["audio_lang_code"] = code
            self._save_config()
            self._refresh_model_dropdown()

    def _on_model_change(self, _event=None):
        disp = self.model_var.get()
        cli = getattr(self, "_model_cli_by_display", {}).get(disp)
        if cli:
            self.cfg["model_cli"] = cli
            self._save_config()
            self._refresh_model_status_label()

    def _on_task_change(self, _event=None):
        idx = self.task_combo.current()
        self.cfg["task"] = "translate" if idx == 1 else "transcribe"
        self._save_config()

    def _on_outdir_mode_change(self):
        self.cfg["output_dir_mode"] = self.outdir_mode_var.get()
        self._save_config()

    def _browse_fixed_dir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.fixed_dir_var.set(d)
            self.cfg["fixed_output_dir"] = d
            self.outdir_mode_var.set("fixed")
            self.cfg["output_dir_mode"] = "fixed"
            self._save_config()

    def _browse_md_fixed_dir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.md_fixed_dir_var.set(d)
            self.md_outdir_mode_var.set("fixed")

    # ======================================================================
    # Queue operations (transcription)
    # ======================================================================
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title=self.t("select_media_title"),
            filetypes=[(self.t("media_files"), " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        if not paths:
            return
        existing = {it.filepath for it in self.queue_items}
        candidate_paths = [p for p in paths if p not in existing]
        if paths and not candidate_paths:
            messagebox.showinfo(self.t("info"), self.t("info_all_in_queue"))
            return
        accepted_paths, overrides = self._resolve_duplicate_transcripts(candidate_paths)
        added = 0
        new_items = []
        for p in accepted_paths:
            it = QueueItem(p)
            if p in overrides:
                it.output_stem_override = overrides[p]
            if self.is_running and getattr(self, "live_queue", None) is not None:
                self.live_queue.add(it)   # locked: safe while worker reads
            else:
                self.queue_items.append(it)
            new_items.append(it)
            added += 1
        self._render_queue()
        self._update_trans_summary()
        if new_items:
            self._probe_media_lengths(new_items)
            if self.is_running:
                self._recompute_trans_total_seconds()

    def _recompute_trans_total_seconds(self):
        """Re-sum known durations across the live queue; called after a
        mid-batch add so percent/ETA reflect the new total (item 1)."""
        total, n_known, total_seconds = queue_length_summary(self.queue_items)
        self._trans_total_seconds = total_seconds

    def _resolve_duplicate_transcripts(self, paths):
        """Item 10: detect files in `paths` that already have a transcript
        (.md/.srt/.txt/.json) next to them. Shows one summary dialog for the
        whole batch. Returns (accepted_paths, overrides) where overrides maps
        filepath -> forced output stem (e.g. "name_2") for files the user
        chose to transcribe anyway."""
        conflicts = []   # list of (path, [exts])
        for p in paths:
            found = find_existing_transcripts(p)
            if found:
                conflicts.append((p, found))
        if not conflicts:
            return paths, {}
        choice = self._show_duplicate_transcript_dialog(conflicts)
        overrides = {}
        if choice == "skip":
            skip_set = {p for p, _ in conflicts}
            accepted = [p for p in paths if p not in skip_set]
        elif choice == "proceed":
            accepted = list(paths)
            for p, _ in conflicts:
                overrides[p] = next_available_suffixed_stem(p)
        else:   # cancel
            accepted = [p for p in paths if p not in {c[0] for c in conflicts}]
        return accepted, overrides

    def _show_duplicate_transcript_dialog(self, conflicts):
        """Returns 'skip', 'proceed', or 'cancel'."""
        win = tk.Toplevel(self)
        win.title(self.t("dup_dialog_title"))
        win.transient(self)
        win.geometry("560x380")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=14, pady=14)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("dup_dialog_intro", n=len(conflicts)),
                  wraplength=520, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 8))
        listf = ttk.Frame(frm)
        listf.grid(row=1, column=0, sticky="nsew")
        listf.columnconfigure(0, weight=1)
        listf.rowconfigure(0, weight=1)
        txt = tk.Text(listf, wrap="word", height=10, font=("TkFixedFont", 9))
        txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(listf, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        for p, exts in conflicts:
            txt.insert("end", f"{os.path.basename(p)}  ({', '.join('.' + e for e in exts)})\n")
        txt.configure(state="disabled")
        result = {"choice": "cancel"}
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e", pady=(10, 0))

        def pick(choice):
            result["choice"] = choice
            win.destroy()
        ttk.Button(btns, text=self.t("dup_skip_btn"),
                  command=lambda: pick("skip")).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("dup_proceed_btn"),
                  command=lambda: pick("proceed")).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("cancel"),
                  command=lambda: pick("cancel")).pack(side="left", padx=2)
        try:
            win.grab_set()
        except tk.TclError:
            pass
        self.wait_window(win)
        return result["choice"]

    def _remove_selected(self):
        locked_selected = False
        ids_to_remove = []
        by_id = {it.item_id: it for it in self.queue_items}
        for iid in self.tree.selection():
            it = by_id.get(int(iid))
            if it is None:
                continue
            if it.status != ST_PENDING:
                locked_selected = True
                continue
            ids_to_remove.append(it.item_id)
        for item_id in ids_to_remove:
            if self.is_running and getattr(self, "live_queue", None) is not None:
                self.live_queue.remove(item_id)   # locked: safe while worker reads
            else:
                self.queue_items = [it for it in self.queue_items
                                    if it.item_id != item_id]
        if ids_to_remove:
            self._render_queue()
            self._update_trans_summary()
            if self.is_running:
                self._recompute_trans_total_seconds()
        if locked_selected:
            messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))

    def _clear_queue(self):
        if self.is_running:
            # Button is disabled while running; this is a defensive fallback.
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.queue_items = []
        self._render_queue()
        self._update_trans_summary()

    def _move_selected(self, direction):
        sel = self.tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        if self.is_running and getattr(self, "live_queue", None) is not None:
            moved = self.live_queue.move(moving_id, direction)
            if not moved:
                target = next((it for it in self.queue_items if it.item_id == moving_id), None)
                if target is not None and target.status != ST_PENDING:
                    messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))
                return
            self._render_queue()
            self.tree.selection_set(str(moving_id))
            return
        by_id = {it.item_id: i for i, it in enumerate(self.queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if not (0 <= new < len(self.queue_items)):
            return
        self.queue_items[idx], self.queue_items[new] = \
            self.queue_items[new], self.queue_items[idx]
        self._render_queue()
        self.tree.selection_set(str(moving_id))

    def _status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_queue(self):
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.queue_items):
            length = fmt_hms(it.duration) if it.duration else "…"
            self.tree.insert("", "end", iid=str(it.item_id),
                             values=(i + 1, it.filename,
                                     os.path.dirname(it.filepath),
                                     length,
                                     self._status_text(it.status)))

    # ======================================================================
    # Queue operations (MD tab)
    # ======================================================================
    def _md_add_files(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        paths = filedialog.askopenfilenames(
            title=self.t("select_doc_title"),
            filetypes=[(self.t("doc_files"), " ".join("*" + e for e in MARKITDOWN_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        existing = {it.filepath for it in self.md_queue_items}
        for p in paths:
            if p not in existing:
                it = QueueItem(p)
                try:
                    it.size_bytes = os.path.getsize(p)
                except OSError:
                    it.size_bytes = None
                self.md_queue_items.append(it)
        self._render_md_queue()
        self._update_md_summary()

    def _md_remove_selected(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for iid in self.md_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.md_queue_items):
                self.md_queue_items[idx] = None
        self.md_queue_items = [it for it in self.md_queue_items if it is not None]
        self._render_md_queue()
        self._update_md_summary()

    def _md_clear_queue(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.md_queue_items = []
        self._render_md_queue()
        self._update_md_summary()

    def _md_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_md"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_md_queue(self):
        self.md_tree.delete(*self.md_tree.get_children())
        for i, it in enumerate(self.md_queue_items):
            size = self._human_bytes(it.size_bytes) if it.size_bytes else "—"
            self.md_tree.insert("", "end", iid=str(i),
                                values=(i + 1, it.filename,
                                        os.path.dirname(it.filepath),
                                        size,
                                        self._md_status_text(it.status)))

    # ======================================================================
    # Dictionary operations
    # ======================================================================
    def _refresh_dict_listbox(self):
        self.dict_listbox.delete(0, "end")
        for name in sorted(self.dictionaries.keys()):
            self.dict_listbox.insert("end", name)

    def _on_dict_profile_select(self, _event=None):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        prof = self.dictionaries.get(name, {})
        self._dict_current = name
        self.dict_name_var.set(name)
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_prompt_text.insert("1.0", prof.get("initial_prompt") or prof.get("prompt") or "")
        self.dict_repl_text.delete("1.0", "end")
        repl = prof.get("replacements", [])
        self.dict_repl_text.insert("1.0", "\n".join(f"{a}={b}" for a, b in repl))

    def _dict_new(self):
        self._dict_current = None
        self.dict_name_var.set("")
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_repl_text.delete("1.0", "end")
        self.dict_listbox.selection_clear(0, "end")

    def _dict_duplicate(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            messagebox.showinfo(self.t("info"), self.t("select_to_duplicate"))
            return
        name = self.dict_listbox.get(sel[0])
        new_name = simpledialog.askstring(
            self.t("dup_title"), self.t("dup_prompt"),
            initialvalue=name + self.t("dup_suffix"), parent=self)
        if not new_name:
            return
        if new_name in self.dictionaries:
            messagebox.showerror(self.t("error"), self.t("err_dup_exists"))
            return
        self.dictionaries[new_name] = json.loads(json.dumps(self.dictionaries[name]))
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._refresh_dict_listbox()
        self._refresh_dictionary_dropdown()

    def _dict_delete(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        if messagebox.askyesno(self.t("confirm"), self.t("delete_question", name=name)):
            self.dictionaries.pop(name, None)
            save_json(DICTIONARIES_FILE, self.dictionaries)
            self._dict_new()
            self._refresh_dict_listbox()
            self._refresh_dictionary_dropdown()

    def _dict_save(self):
        name = self.dict_name_var.get().strip()
        if not name:
            messagebox.showerror(self.t("error"), self.t("err_no_profile_name"))
            return
        prompt = self.dict_prompt_text.get("1.0", "end").strip()
        repl = parse_replacements_text(self.dict_repl_text.get("1.0", "end"))
        if self._dict_current and self._dict_current != name:
            self.dictionaries.pop(self._dict_current, None)
        self.dictionaries[name] = {"initial_prompt": prompt, "replacements": repl}
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._dict_current = name
        self._refresh_dict_listbox()
        self._refresh_dictionary_dropdown()
        messagebox.showinfo(self.t("saved"), self.t("profile_saved_msg", name=name))

    # ======================================================================
    # Streaming helpers for dialogs
    # ======================================================================
    def _append_text(self, widget, text):
        try:
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.see("end")
            widget.configure(state="disabled")
        except tk.TclError:
            pass

    def _attach_stream(self, event_queue, log_text, on_finish):
        def poll():
            try:
                while True:
                    ev = event_queue.get_nowait()
                    k = ev.get("kind")
                    if k in ("log", "cmd_log", "md_log"):
                        self._append_text(log_text, ev.get("text", ""))
                    elif k == "dl_model_ok":
                        self._append_text(log_text, self.t("log_model_ok"))
                    elif k == "dl_finished":
                        on_finish(bool(ev.get("success")), ev.get("error", ""))
                        return
                    elif k == "cmd_finished":
                        rc = ev.get("returncode", 0)
                        on_finish(rc == 0, "" if rc == 0 else str(rc))
                        return
            except queue.Empty:
                pass
            self.after(120, poll)
        poll()

    # ======================================================================
    # Settings: Whisper
    # ======================================================================
    def _open_whisper_settings(self, focus=None):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_whisper_title"))
        dlg.transient(self)
        dlg.geometry("760x640")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)

        # status
        status_var = tk.StringVar()

        def refresh_status():
            self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
            if self.whisper_path:
                status_var.set(self.t("set_whisper_found", path=self.whisper_path))
            else:
                status_var.set(self.t("set_whisper_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=720).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # executable row
        exrow = ttk.LabelFrame(frm, text=self.t("set_whisper_exe"))
        exrow.grid(row=1, column=0, sticky="ew", pady=4)
        exrow.columnconfigure(0, weight=1)
        exe_var = tk.StringVar(value=self.cfg.get("whisper_path", ""))
        ttk.Entry(exrow, textvariable=exe_var).grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        def browse_exe():
            p = filedialog.askopenfilename(title=self.t("select_whisper_title"), parent=dlg)
            if p:
                exe_var.set(p)
                self.cfg["whisper_path"] = p
                self._save_config()
                refresh_status()
        ttk.Button(exrow, text=self.t("browse"), command=browse_exe).grid(row=0, column=1, padx=4, pady=6)

        # models manager
        mf = ttk.LabelFrame(frm, text=self.t("set_models_title"))
        mf.grid(row=2, column=0, sticky="nsew", pady=4)
        mf.columnconfigure(0, weight=1)
        frm.rowconfigure(2, weight=1)
        model_list = tk.Listbox(mf, height=8, exportselection=False)
        model_list.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        mf.rowconfigure(0, weight=1)

        def fill_models():
            model_list.delete(0, "end")
            for cli in ALL_MODEL_CLIS:
                downloaded, _ = is_model_downloaded(cli)
                tag = self.t("installed_tag") if downloaded else ""
                model_list.insert("end", f"{cli}{tag}  —  {self.t(MODEL_INFO[cli]['desc_key'])}")
        fill_models()

        dl_log = tk.Text(mf, height=6, wrap="word", state="disabled", font=("TkFixedFont", 9))
        dl_log.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        def download_model():
            sel = model_list.curselection()
            if not sel:
                return
            cli = ALL_MODEL_CLIS[sel[0]]
            if not self.whisper_path:
                messagebox.showerror(self.t("error"), self.t("err_no_whisper"), parent=dlg)
                return
            info = MODEL_INFO[cli]
            self._append_text(dl_log, self.t("log_download_start",
                                             model=cli, size=human_size(info["size_mb"])))
            stop = threading.Event()
            q = queue.Queue()
            worker = ModelDownloadWorker(self.whisper_path, cli, q, stop)
            dl_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                dl_btn.configure(state="normal")
                if not success and error:
                    self._append_text(dl_log, f"\n[ERROR] {error}\n")
                fill_models()
                self._refresh_model_dropdown()
            self._attach_stream(q, dl_log, done)
        dl_btn = ttk.Button(mf, text=self.t("set_models_download"), command=download_model)
        dl_btn.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 6))

        # install whisper
        irow = ttk.Frame(frm)
        irow.grid(row=3, column=0, sticky="ew", pady=4)
        install_log = tk.Text(irow, height=5, wrap="word", state="disabled", font=("TkFixedFont", 9))

        def install_whisper():
            py = find_python_executable()
            cmd = build_pip_install_command(py, "openai-whisper")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_whisper_install_q", cmd=" ".join(cmd)),
                                       parent=dlg):
                return
            install_log.grid(row=1, column=0, sticky="ew", pady=(4, 0))
            self._append_text(install_log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="whisper")
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                inst_btn.configure(state="normal")
                self._append_text(install_log,
                                  self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
                self._refresh_model_dropdown()
            self._attach_stream(q, install_log, done)
        irow.columnconfigure(0, weight=1)
        inst_btn = ttk.Button(irow, text=self.t("set_whisper_install"), command=install_whisper)
        inst_btn.grid(row=0, column=0, sticky="w")

        # languages manager
        lf = ttk.LabelFrame(frm, text=self.t("set_langs_title"))
        lf.grid(row=4, column=0, sticky="ew", pady=4)
        lf.columnconfigure(0, weight=1)
        lang_list = tk.Listbox(lf, height=5, exportselection=False)
        lang_list.grid(row=0, column=0, rowspan=2, sticky="ew", padx=6, pady=6)

        def fill_langs():
            lang_list.delete(0, "end")
            for c in self.cfg.get("audio_langs", []):
                lang_list.insert("end", self._audio_lang_display(c))
        fill_langs()

        addrow = ttk.Frame(lf)
        addrow.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        ttk.Label(addrow, text=self.t("set_lang_pick")).pack(side="left")
        all_lang_displays = [f"{name} ({code})" for code, name in
                             sorted(WHISPER_LANGUAGES.items(), key=lambda kv: kv[1])]
        add_var = tk.StringVar()
        add_combo = ttk.Combobox(addrow, textvariable=add_var, values=all_lang_displays,
                                 state="readonly", width=28)
        add_combo.pack(side="left", padx=6)

        def add_lang():
            disp = add_var.get()
            m = re.search(r"\(([a-z]{2,3})\)\s*$", disp)
            if not m:
                return
            code = m.group(1)
            if code not in self.cfg["audio_langs"]:
                self.cfg["audio_langs"].append(code)
                self._save_config()
                fill_langs()
                self._refresh_audio_lang_dropdown()
                self._refresh_model_dropdown()
        ttk.Button(addrow, text=self.t("set_lang_add"), command=add_lang).pack(side="left", padx=4)

        def remove_lang():
            sel = lang_list.curselection()
            if not sel:
                return
            code = self.cfg["audio_langs"][sel[0]]
            self.cfg["audio_langs"].pop(sel[0])
            if not self.cfg["audio_langs"]:
                self.cfg["audio_langs"] = ["auto"]
            if self.cfg.get("audio_lang_code") == code:
                self.cfg["audio_lang_code"] = self.cfg["audio_langs"][0]
            self._save_config()
            fill_langs()
            self._refresh_audio_lang_dropdown()
            self._refresh_model_dropdown()
        ttk.Button(lf, text=self.t("set_lang_remove"), command=remove_lang
                   ).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=5, column=0, sticky="e", pady=8)
        refresh_status()
        if focus == "models":
            try:
                model_list.focus_set()
            except tk.TclError:
                pass
        elif focus == "langs":
            try:
                lang_list.focus_set()
            except tk.TclError:
                pass

    # ======================================================================
    # Settings: MarkItDown
    # ======================================================================
    def _open_markitdown_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_markitdown_title"))
        dlg.transient(self)
        dlg.geometry("680x460")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        ttk.Label(frm, text=self.t("set_markitdown_about"), foreground="#555",
                  wraplength=640).grid(row=0, column=0, sticky="w", pady=(0, 6))
        status_var = tk.StringVar()

        def refresh_status():
            self.python_exe = markitdown_python(self.cfg)
            self.markitdown_ok = markitdown_is_available(self.python_exe)
            if self.markitdown_ok:
                status_var.set(self.t("set_markitdown_found", py=self.python_exe))
            else:
                status_var.set(self.t("set_markitdown_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=640).grid(row=1, column=0, sticky="w", pady=4)

        btnrow = ttk.Frame(frm)
        btnrow.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def install_md():
            py = find_python_executable()
            cmd = build_pip_install_command(py, "markitdown[all]")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_markitdown_install_q", cmd=" ".join(cmd)),
                                       parent=dlg):
                return
            self._append_text(log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="md")
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                inst_btn.configure(state="normal")
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
            self._attach_stream(q, log, done)
        inst_btn = ttk.Button(btnrow, text=self.t("set_markitdown_install"), command=install_md)
        inst_btn.pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_recheck"), command=refresh_status).pack(side="left", padx=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=4, column=0, sticky="e", pady=6)
        refresh_status()

    # ======================================================================
    # Settings: FFmpeg
    # ======================================================================
    def _open_ffmpeg_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_ffmpeg_title"))
        dlg.transient(self)
        dlg.geometry("700x500")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        status_var = tk.StringVar()

        def refresh_status():
            self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
            if self.ffmpeg_path:
                status_var.set(self.t("set_ffmpeg_found", path=self.ffmpeg_path))
            else:
                status_var.set(self.t("set_ffmpeg_missing"))
            self._refresh_status_indicators()
            self._update_clip_gate()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=660).grid(row=0, column=0, sticky="w", pady=(0, 6))

        row1 = ttk.Frame(frm)
        row1.grid(row=1, column=0, sticky="w", pady=4)

        def locate():
            p = filedialog.askopenfilename(title=self.t("select_ffmpeg_title"), parent=dlg)
            if p:
                self.cfg["ffmpeg_path"] = p
                self._save_config()
                refresh_status()
        ttk.Button(row1, text=self.t("ffmpeg_locate"), command=locate).pack(side="left", padx=2)

        def open_folder():
            self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
            if self.ffmpeg_path:
                self._open_path(os.path.dirname(self.ffmpeg_path))
        ttk.Button(row1, text=self.t("ffmpeg_open_folder"), command=open_folder).pack(side="left", padx=2)

        row2 = ttk.Frame(frm)
        row2.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def auto_install():
            dest = str(FFMPEG_INSTALL_DIR)
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_ffmpeg_auto_q", dest=dest), parent=dlg):
                return
            auto_btn.configure(state="disabled")
            self._start_ffmpeg_auto(log, lambda ok, path: (
                auto_btn.configure(state="normal"), refresh_status()))

        def winget_install():
            cmd = ["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                   "--accept-package-agreements", "--accept-source-agreements"]
            self._append_text(log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="ffmpeg")
            worker.start()

            def done(success, error):
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
            self._attach_stream(q, log, done)

        auto_btn = ttk.Button(row2, text=self.t("set_ffmpeg_install_auto"), command=auto_install)
        auto_btn.pack(side="left", padx=2)
        if os.name == "nt":
            ttk.Button(row2, text=self.t("set_ffmpeg_winget"), command=winget_install).pack(side="left", padx=2)
        ttk.Button(row2, text=self.t("set_ffmpeg_open_page"),
                   command=lambda: webbrowser.open(FFMPEG_DOWNLOAD_URL)).pack(side="left", padx=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=4, column=0, sticky="e", pady=6)
        refresh_status()

    def _start_ffmpeg_auto(self, log_text, on_finish):
        q = queue.Queue()

        def work():
            try:
                FFMPEG_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
                url = FFMPEG_WIN_BUILD_URL
                q.put(("log", self.t("set_ffmpeg_downloading")))
                tmp = FFMPEG_INSTALL_DIR / "ffmpeg_download.zip"
                urllib.request.urlretrieve(url, str(tmp))
                q.put(("log", self.t("set_ffmpeg_extracting")))
                exe = extract_ffmpeg_archive(str(tmp), FFMPEG_INSTALL_DIR)
                try:
                    tmp.unlink()
                except OSError:
                    pass
                if not exe:
                    raise RuntimeError("ffmpeg executable not found in archive")
                self.cfg["ffmpeg_path"] = exe
                self._save_config()
                q.put(("done", exe))
            except Exception as e:
                q.put(("fail", str(e)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                while True:
                    k, v = q.get_nowait()
                    if k == "log":
                        self._append_text(log_text, v)
                    elif k == "done":
                        self._append_text(log_text, self.t("set_ffmpeg_done", path=v))
                        on_finish(True, v)
                        return
                    elif k == "fail":
                        self._append_text(log_text, self.t("set_ffmpeg_fail", e=v))
                        on_finish(False, v)
                        return
            except queue.Empty:
                pass
            self.after(150, poll)
        poll()

    # ======================================================================
    # Settings: Output formats
    # ======================================================================
    def _open_output_formats(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("output_formats_title"))
        dlg.transient(self)
        dlg.geometry("640x360")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        ttk.Label(frm, text=self.t("output_formats")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.format_vars = {}
        for i, fmt in enumerate(OUTPUT_FORMATS):
            var = tk.BooleanVar(value=self.cfg["output_formats"].get(fmt, True))
            self.format_vars[fmt] = var

            def make_cb(f=fmt, v=var):
                def cb():
                    self.cfg["output_formats"][f] = v.get()
                    self._save_config()
                return cb
            ttk.Checkbutton(frm, text=self.t("fmt_" + fmt), variable=var,
                            command=make_cb()).grid(row=i + 1, column=0, sticky="w", pady=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy
                   ).grid(row=len(OUTPUT_FORMATS) + 1, column=0, sticky="e", pady=10)

    # ======================================================================
    # About
    # ======================================================================
    def _open_about(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("about_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=24, pady=20)
        try:
            ttk.Label(frm, image=self._icon_img_large).pack(pady=(0, 8))
        except Exception:
            pass
        ttk.Label(frm, text=APP_NAME, font=("TkDefaultFont", 16, "bold")).pack()
        ttk.Label(frm, text=f"{self.t('about_version')}: {APP_VERSION}").pack(pady=(8, 0))
        ttk.Label(frm, text=f"{self.t('about_author')}: {APP_AUTHOR}").pack()
        contact_row = ttk.Frame(frm)
        contact_row.pack()
        ttk.Label(contact_row, text=f"{self.t('about_contact')}: ").pack(side="left")
        email = tk.Label(contact_row, text=APP_CONTACT, fg="#0a58ca",
                         cursor="hand2", font=("TkDefaultFont", 9, "underline"))
        email.pack(side="left")
        email.bind("<Button-1>", lambda e: self._open_contact_email())
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).pack(pady=(16, 0))

    def _open_contact_email(self):
        try:
            webbrowser.open("mailto:" + APP_CONTACT)
        except Exception:
            pass

    # ======================================================================
    # Open helpers
    # ======================================================================
    def _open_path(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # noqa
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _open_output_folder(self):
        for it in self.queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return

    def _md_open_output_folder(self):
        for it in self.md_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return

    # ======================================================================
    # Transcription run
    # ======================================================================
    def _selected_keep_formats(self):
        return [f for f in OUTPUT_FORMATS if self.cfg["output_formats"].get(f, False)]

    def _selected_dictionary_payload(self):
        name = self.dict_var.get()
        if not name or name == self.t("none"):
            return "", []
        prof = self.dictionaries.get(name, {})
        return (prof.get("initial_prompt") or prof.get("prompt") or ""), prof.get("replacements", [])

    def _validate_clip(self):
        if not self.clip_enabled_var.get():
            return None, None
        if not self.ffmpeg_path:
            return None, "err_clip_needs_ffmpeg"
        start = parse_hms_to_seconds(self.clip_start_var.get())
        end = parse_hms_to_seconds(self.clip_end_var.get())
        if start is None or end is None or end <= start:
            return None, "err_clip_invalid"
        return (start, end), None

    def _start_batch(self):
        if self.is_running:
            return
        if not self.queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self.whisper_path:
            messagebox.showerror(self.t("error"), self.t("err_no_whisper"))
            self._open_whisper_settings()
            return
        installed = models_for_audio_language(
            self.cfg.get("audio_lang_code", "pt"), only_installed=True)
        model = self.cfg.get("model_cli", "")
        if not installed or model not in installed:
            messagebox.showerror(self.t("error"), self.t("err_no_model_selected"))
            self._open_whisper_settings(focus="models")
            return
        keep = self._selected_keep_formats()
        if not keep:
            messagebox.showerror(self.t("error"), self.t("err_no_format"))
            self._open_output_formats()
            return
        if self.outdir_mode_var.get() == "fixed" and not self.fixed_dir_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
            return
        clip_range, clip_err = self._validate_clip()
        if clip_err:
            messagebox.showerror(self.t("error"), self.t(clip_err))
            return
        if not self.ffmpeg_path:
            if not messagebox.askyesno(self.t("warn"), self.t("ffmpeg_missing_warn")):
                return

        # reset statuses
        for it in self.queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_queue()

        prompt, replacements = self._selected_dictionary_payload()
        lang_param = audio_lang_param(self.cfg.get("audio_lang_code", "pt"))
        task = self.cfg.get("task", "transcribe")

        self.stop_flag = threading.Event()
        self.live_queue = LiveQueue(self.queue_items)
        self.worker = TranscriptionWorker(
            live_queue=self.live_queue, whisper_exe=self.whisper_path,
            ffmpeg_path=self.ffmpeg_path, lang_param=lang_param, task=task,
            model_name=model, initial_prompt=prompt, replacements=replacements,
            keep_formats=keep, output_dir_mode=self.outdir_mode_var.get(),
            fixed_output_dir=self.fixed_dir_var.get().strip(),
            clip_range=clip_range, strings=self.s,
            event_queue=self.event_queue, stop_flag=self.stop_flag)
        self.is_running = True
        self._batch_start_time = time.time()
        self._batch_done = 0
        self._batch_errors = 0
        self._cur_duration = None
        self._batch_model = model
        total, n_known, total_seconds = queue_length_summary(self.queue_items)
        self._trans_total_seconds = total_seconds
        self._trans_done_seconds = 0.0
        self._cur_position = 0.0
        self._cur_running_id = None
        self._set_progress(self.progress, self.progress_pct_var, 0.0)
        self._set_running_ui(True)
        self._clear_log(self.log_text)
        self._append_text(self.log_text, self.t("log_batch_start",
                                                time=datetime.now().strftime("%H:%M:%S")))
        self.worker.start()

    def _cancel_batch(self):
        if self.is_running and self.worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.log_text, self.t("log_canceling"))
                self.worker.cancel()

    def _set_running_ui(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.open_out_btn.configure(state="disabled" if running else "normal")
        if hasattr(self, "clear_queue_btn"):
            self.clear_queue_btn.configure(state="disabled" if running else "normal")

    def _clear_log(self, widget):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                ev = self.event_queue.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _handle_event(self, ev):
        kind = ev.get("kind")
        if kind == "log":
            self._append_text(self.log_text, ev.get("text", ""))
        elif kind == "item_status":
            item_id = ev.get("item_id")
            status = ev.get("status")
            it = next((q for q in self.queue_items if q.item_id == item_id), None)
            if it is not None:
                it.status = status
                try:
                    self.tree.set(str(item_id), "status", self._status_text(status))
                except tk.TclError:
                    pass   # row may have been removed from the tree already
            if status == ST_RUNNING:
                self._cur_running_id = item_id
                self._cur_position = 0.0
                self._cur_file_start = time.time()
                self._cur_item_duration = it.duration if it is not None else None
                self._update_trans_progress_label()
            elif status in ST_TERMINAL:
                if status == ST_DONE:
                    self._batch_done += 1
                elif status == ST_ERROR:
                    self._batch_errors += 1
                dur = getattr(self, "_cur_item_duration", None)
                if isinstance(dur, (int, float)) and dur > 0:
                    self._trans_done_seconds += float(dur)
                    if status == ST_DONE:
                        wall = time.time() - getattr(self, "_cur_file_start", time.time())
                        if wall > 0:
                            self._set_speed_factor(getattr(self, "_batch_model", ""),
                                                   wall / float(dur))
                self._cur_position = 0.0
                self._cur_item_duration = None
                self._update_trans_progress_label()
        elif kind == "duration":
            self._cur_duration = ev.get("seconds")
            if not getattr(self, "_cur_item_duration", None):
                self._cur_item_duration = ev.get("seconds")
        elif kind == "phase":
            phase = ev.get("phase")
            if phase == "preparing":
                self.progress_label_var.set(self.t("phase_preparing"))
            elif phase == "transcribing":
                self._set_progress(self.progress, self.progress_pct_var,
                                   self._current_trans_percent())
                self.progress_label_var.set(self.t("phase_transcribing_note"))
        elif kind == "progress_tick":
            pos = ev.get("seconds")
            if pos is not None:
                self._cur_position = float(pos)
            self._update_trans_progress_label()
        elif kind == "batch_finished":
            self._on_batch_finished()

    def _current_trans_percent(self):
        total_items = len(self.queue_items)
        done_items = self._batch_done + self._batch_errors
        return compute_batch_percent(
            self._trans_done_seconds, self._cur_position,
            self._trans_total_seconds, done_items, total_items)

    def _update_trans_progress_label(self):
        pct = self._current_trans_percent()
        self._set_progress(self.progress, self.progress_pct_var, pct)
        total_items = max(1, len(self.queue_items))
        done_items = self._batch_done + self._batch_errors
        cur = current_processing_index(done_items, total_items, self.is_running)
        cumulative = self._trans_done_seconds + max(0.0, self._cur_position)
        sf, confident = self._get_speed_factor(getattr(self, "_batch_model", ""))
        # Self-correct mid-file: blend the persisted historical factor with the
        # live wall/audio ratio observed so far in the file currently running,
        # so a long single file's ETA doesn't stay frozen at a stale estimate
        # for its entire duration (the original bug: it only updated *after*
        # a file finished, so an 8h file with a 2h estimate never corrected).
        live_wall = max(0.0, time.time() - getattr(self, "_cur_file_start", time.time()))
        live_pos = max(0.0, self._cur_position)
        if live_pos > 30:   # ignore noisy ratio in the first ~30s of audio progress
            live_sf = live_wall / live_pos
            weight = min(1.0, live_pos / 600.0)   # ramps to full trust over ~10min in
            sf = (1.0 - weight) * sf + weight * live_sf
        eta_txt = "—"
        if self._trans_total_seconds and self._trans_total_seconds > 0:
            remaining = max(0.0, self._trans_total_seconds - cumulative)
            eta_txt = fmt_hms(remaining * max(0.01, sf))
            if not confident:
                eta_txt += " " + self.t("eta_low_confidence_suffix")
        line = (self.t("batch_progress", done=cur, total=total_items)
                + "   ·   " + self.t("status_cur_pos", pos=fmt_hms(self._cur_position))
                + "   ·   " + self.t("status_total_transcribed",
                                     val=fmt_hms(cumulative))
                + "   ·   " + self.t("status_eta_complete", eta=eta_txt))
        self.progress_label_var.set(line)

    def _on_batch_finished(self):
        self.is_running = False
        self.worker = None
        self.live_queue = None
        self._set_progress(self.progress, self.progress_pct_var, 100.0)
        self._set_running_ui(False)
        self._append_text(self.log_text, self.t("log_batch_end",
                                                time=datetime.now().strftime("%H:%M:%S")))
        self.progress_label_var.set(self.t("batch_finished_label",
                                    done=self._batch_done, errors=self._batch_errors))
        if self._batch_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._batch_done, errors=self._batch_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._batch_done))

    # ======================================================================
    # MD batch run
    # ======================================================================
    def _start_md_batch(self):
        if self.md_is_running:
            return
        if not self.md_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        # MarkItDown required only if a non-subtitle file is queued.
        needs_md = any(os.path.splitext(it.filepath)[1].lower() not in SUBTITLE_EXTENSIONS
                       for it in self.md_queue_items)
        if needs_md and not self.markitdown_ok:
            messagebox.showerror(self.t("error"), self.t("err_no_markitdown"))
            self._open_markitdown_settings()
            return
        if self.md_outdir_mode_var.get() == "fixed" and not self.md_fixed_dir_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
            return
        for it in self.md_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_md_queue()
        self.md_stop_flag = threading.Event()
        self.md_worker = ConversionWorker(
            items=self.md_queue_items, python_exe=markitdown_python(self.cfg),
            markitdown_ok=self.markitdown_ok,
            output_dir_mode=self.md_outdir_mode_var.get(),
            fixed_output_dir=self.md_fixed_dir_var.get().strip(),
            strings=self.s, event_queue=self.md_event_queue, stop_flag=self.md_stop_flag)
        self.md_is_running = True
        self._md_done = 0
        self._md_errors = 0
        self._md_total = len(self.md_queue_items)
        self.md_start_btn.configure(state="disabled")
        self.md_cancel_btn.configure(state="normal")
        self.md_open_out_btn.configure(state="disabled")
        self._clear_log(self.md_log_text)
        self._append_text(self.md_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.md_progress.configure(value=0)
        self.md_worker.start()

    def _cancel_md_batch(self):
        if self.md_is_running and self.md_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.md_log_text, self.t("log_canceling"))
                self.md_worker.cancel()

    def _poll_md_events(self):
        try:
            while True:
                ev = self.md_event_queue.get_nowait()
                self._handle_md_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_md_events)

    def _handle_md_event(self, ev):
        kind = ev.get("kind")
        if kind == "md_log":
            self._append_text(self.md_log_text, ev.get("text", ""))
        elif kind == "md_item_status":
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.md_queue_items):
                self.md_queue_items[idx].status = status
                self.md_tree.set(str(idx), "status", self._md_status_text(status))
            if status == ST_RUNNING:
                self._md_cur_index = idx
                self._update_md_progress_label()
            elif status in ST_TERMINAL:
                if status == ST_DONE:
                    self._md_done += 1
                elif status == ST_ERROR:
                    self._md_errors += 1
                self._update_md_progress_label()
        elif kind == "md_batch_finished":
            self._on_md_batch_finished()

    def _update_md_progress_label(self):
        total = max(1, getattr(self, "_md_total", 1))
        done = self._md_done + self._md_errors
        pct = compute_batch_percent(0, 0, 0, done, total)
        self._set_progress(self.md_progress, self.md_progress_pct_var, pct)
        cur = current_processing_index(done, total, self.md_is_running)
        self.md_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_md_batch_finished(self):
        self.md_is_running = False
        self.md_worker = None
        self._set_progress(self.md_progress, self.md_progress_pct_var, 100.0)
        self.md_start_btn.configure(state="normal")
        self.md_cancel_btn.configure(state="disabled")
        self.md_open_out_btn.configure(state="normal")
        self._append_text(self.md_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.md_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._md_done, errors=self._md_errors))
        if self._md_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._md_done, errors=self._md_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._md_done))

    # ======================================================================
    # Language switch / close
    # ======================================================================
    def _switch_language(self, code):
        if code not in TRANSLATIONS or code == self.lang:
            return
        if (self.is_running or self.md_is_running or self.youtube_is_running
                or self.download_is_running or self.grabber_is_running):
            self._menu_lang_var.set(self.lang)
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.lang = code
        self.s = TRANSLATIONS[code]
        self.cfg["ui_language"] = code
        self._save_config()
        self.title(self.s["window_title"])
        self._build_menubar()
        self._build_ui()
        self._render_queue()
        self._render_md_queue()
        self._render_youtube_queue()
        self._render_download_queue()
        self._update_trans_summary()
        self._update_md_summary()
        self._update_youtube_summary()
        self._update_download_summary()

    def _on_close(self):
        if (self.is_running or self.md_is_running or self.youtube_is_running
                or self.download_is_running):
            if not messagebox.askyesno(self.t("exit_title"), self.t("exit_question")):
                return
            if self.worker:
                self.worker.cancel()
            if self.md_worker:
                self.md_worker.cancel()
            if self.youtube_worker and self.youtube_stop_flag:
                self.youtube_stop_flag.set()
            if self.download_worker:
                self.download_worker.cancel()
            if self.grabber_worker and self.grabber_stop_flag:
                self.grabber_stop_flag.set()
        self.destroy()


def main():
    app = TranscriptLabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
