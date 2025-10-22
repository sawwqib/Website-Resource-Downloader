
# Threaded Website Mirror

A powerful, multi-threaded website mirroring tool. Download entire websites for offline browsing with all resources intact.

## ✨ Features
🚀 Multi-threaded downloading - Download multiple pages simultaneously

🔗 Smart link conversion - All links converted for offline use

🖼️ Complete resource download - Images, CSS, JavaScript, and more

📁 Organized file structure - Clean mirror directory layout

🎯 Domain filtering - Only downloads from target domain

💾 HTML extension handling - Automatic .html extension addition

## 📋 Requirements
Python 3.6+

Termux (Android) or any Linux terminal

Internet connection

## 🔧 Installation
```
git clone https://github.com/sawwqib/Website-Resource-Downloader.git

cd Website-Resource-Downloader

# Install dependencies
pip install -r requirements.txt
```
## 🚀 Usage
```
python3 main.py https://example.com
```
## Advanced Options

### Use 20 threads with 0.5 second delay
```
python main.py https://example.com -t 20 -d 0.5
```
### Enable verbose logging
```
python main.py https://example.com -v
```
### Full example with all options
```
python main.py https://example.com -t 15 -d 0.2 -v --no-banner
```
### Repo Visits
![Visitor Count](https://count.getloli.com/@websitedwnldr?name=websitedwnldr&theme=random&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)
