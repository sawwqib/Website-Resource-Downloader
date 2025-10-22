import os
import sys
import threading
import queue
import requests
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
from pathlib import Path
import time
import argparse
import logging
from typing import Set, Dict, List

# Color codes for Termux
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Banner art
BANNER = f"""
{Colors.CYAN}{Colors.BOLD}

██╗    ██╗     ██████╗██╗      ██████╗ ███╗   ██╗███████╗
██║    ██║    ██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
██║ █╗ ██║    ██║     ██║     ██║   ██║██╔██╗ ██║█████╗  
██║███╗██║    ██║     ██║     ██║   ██║██║╚██╗██║██╔══╝  
╚███╔███╔╝    ╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
 ╚══╝╚══╝      ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
                             
║══════════════════════════════════════════════════════════════════════════║                                                                          ║  
║                                                                          ║
║         {Colors.MAGENTA}THREADED WEBSITE MIRROR{Colors.CYAN}             ║  
║	 {Colors.YELLOW}Created By @sawwqib{Colors.CYAN}                   ║
║══════════════════════════════════════════════════════════════════════════║                 
{Colors.END}
"""

# Configure logging with colors
class ColoredFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: Colors.CYAN + "%(asctime)s - %(levelname)s - %(message)s" + Colors.END,
        logging.INFO: Colors.GREEN + "%(asctime)s - %(levelname)s - %(message)s" + Colors.END,
        logging.WARNING: Colors.YELLOW + "%(asctime)s - %(levelname)s - %(message)s" + Colors.END,
        logging.ERROR: Colors.RED + "%(asctime)s - %(levelname)s - %(message)s" + Colors.END,
        logging.CRITICAL: Colors.RED + Colors.BOLD + "%(asctime)s - %(levelname)s - %(message)s" + Colors.END
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def print_banner():
    """Print the awesome banner"""
    print(BANNER)

def print_status(message, color=Colors.YELLOW):
    """Print status messages with colors"""
    print(f"{color}{Colors.BOLD}[*]{Colors.END} {color}{message}{Colors.END}")

def print_success(message):
    """Print success messages"""
    print(f"{Colors.GREEN}{Colors.BOLD}[+]{Colors.END} {Colors.GREEN}{message}{Colors.END}")

def print_error(message):
    """Print error messages"""
    print(f"{Colors.RED}{Colors.BOLD}[-]{Colors.END} {Colors.RED}{message}{Colors.END}")

def print_info(message):
    """Print info messages"""
    print(f"{Colors.CYAN}{Colors.BOLD}[i]{Colors.END} {Colors.CYAN}{message}{Colors.END}")

class WebsiteMirror:
    def __init__(self, base_url: str, max_threads: int = 10, delay: float = 0.1):
        self.base_url = base_url.rstrip('/')
        self.max_threads = max_threads
        self.delay = delay
        
        # Parse base URL to get domain and base directory
        parsed_url = urlparse(base_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme or 'https'
        self.base_path = parsed_url.path
        
        # Create base directory for the mirror
        self.mirror_dir = Path(f"mirror_{self.domain}")
        self.mirror_dir.mkdir(exist_ok=True)
        
        # Threading components
        self.url_queue = queue.Queue()
        self.visited_urls: Set[str] = set()
        self.visited_lock = threading.Lock()
        self.resource_map: Dict[str, str] = {}
        
        # Statistics
        self.stats = {
            'pages_downloaded': 0,
            'resources_downloaded': 0,
            'errors': 0,
            'start_time': 0
        }
        self.stats_lock = threading.Lock()
        
        # Add the base URL to start crawling
        self.url_queue.put(base_url)
        self.visited_urls.add(base_url)

    def should_download(self, url: str) -> bool:
        """Check if URL belongs to the same domain and should be downloaded"""
        parsed = urlparse(url)
        return parsed.netloc == self.domain or not parsed.netloc

    def get_local_path(self, url: str, is_resource: bool = False) -> Path:
        """Convert URL to local file path"""
        parsed = urlparse(url)
        
        # Build file path
        if parsed.path == '' or parsed.path == '/':
            path = self.mirror_dir / 'index.html'
        else:
            clean_path = parsed.path.lstrip('/')
            file_path = Path(clean_path)
            
            # Add .html extension for pages if not present and not a resource
            if not is_resource and not file_path.suffix:
                file_path = file_path.with_suffix('.html')
            
            local_path = self.mirror_dir / file_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            path = local_path
        
        return path

    def download_file(self, url: str, local_path: Path) -> bool:
        """Download a file from URL to local path"""
        try:
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            print_error(f"Failed to download {url}: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
            return False

    def process_html(self, content: str, base_url: str) -> str:
        """Process HTML content to convert links for offline use"""
        soup = BeautifulSoup(content, 'html.parser')
        
        # Update all links
        for tag in soup.find_all(['a', 'link']):
            if tag.get('href'):
                original_url = tag['href']
                absolute_url = urljoin(base_url, original_url)
                
                if self.should_download(absolute_url):
                    local_path = self.get_local_path(absolute_url)
                    relative_path = os.path.relpath(local_path, self.mirror_dir)
                    tag['href'] = relative_path
                    
                    # Add to queue if not visited
                    with self.visited_lock:
                        if absolute_url not in self.visited_urls:
                            self.visited_urls.add(absolute_url)
                            self.url_queue.put(absolute_url)
        
        # Update all resource links (images, scripts, styles)
        for tag in soup.find_all(['img', 'script', 'source']):
            attr = 'src' if tag.get('src') else 'data-src'
            if tag.get(attr):
                original_url = tag[attr]
                absolute_url = urljoin(base_url, original_url)
                
                if self.should_download(absolute_url):
                    local_path = self.get_local_path(absolute_url, is_resource=True)
                    relative_path = os.path.relpath(local_path, self.mirror_dir)
                    tag[attr] = relative_path
                    
                    # Download resource
                    if absolute_url not in self.resource_map:
                        self.resource_map[absolute_url] = str(local_path)
                        if self.download_file(absolute_url, local_path):
                            with self.stats_lock:
                                self.stats['resources_downloaded'] += 1
        
        # Update CSS links
        for tag in soup.find_all('link', rel='stylesheet'):
            if tag.get('href'):
                original_url = tag['href']
                absolute_url = urljoin(base_url, original_url)
                
                if self.should_download(absolute_url):
                    local_path = self.get_local_path(absolute_url, is_resource=True)
                    relative_path = os.path.relpath(local_path, self.mirror_dir)
                    tag['href'] = relative_path
                    
                    # Download CSS file
                    if absolute_url not in self.resource_map:
                        self.resource_map[absolute_url] = str(local_path)
                        if self.download_file(absolute_url, local_path):
                            with self.stats_lock:
                                self.stats['resources_downloaded'] += 1
        
        return str(soup)

    def process_url(self, url: str):
        """Process a single URL - download and extract links"""
        try:
            # Be polite - add delay between requests
            time.sleep(self.delay)
            
            print_status(f"Processing: {url}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            
            local_path = self.get_local_path(url)
            
            if 'text/html' in content_type:
                # Process HTML content
                processed_content = self.process_html(response.text, url)
                
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                
                with self.stats_lock:
                    self.stats['pages_downloaded'] += 1
                
                print_success(f"Downloaded and processed: {url}")
                
            else:
                # Download non-HTML content directly
                if self.download_file(url, local_path):
                    with self.stats_lock:
                        self.stats['resources_downloaded'] += 1
                    print_success(f"Downloaded resource: {url}")
            
        except Exception as e:
            print_error(f"Error processing {url}: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1

    def worker(self):
        """Worker thread function"""
        while True:
            try:
                url = self.url_queue.get(timeout=10)
                self.process_url(url)
                self.url_queue.task_done()
            except queue.Empty:
                break

    def show_progress(self):
        """Show real-time progress"""
        while not self.url_queue.empty() or threading.active_count() > 1:
            with self.stats_lock:
                pages = self.stats['pages_downloaded']
                resources = self.stats['resources_downloaded']
                errors = self.stats['errors']
                elapsed = time.time() - self.stats['start_time']
            
            print_info(f"Progress: {pages} pages, {resources} resources, {errors} errors | Queue: {self.url_queue.qsize()} | Time: {elapsed:.1f}s")
            time.sleep(2)

    def mirror(self):
        """Main function to start the mirroring process"""
        print_info(f"Starting mirror of {Colors.BOLD}{self.base_url}{Colors.END}")
        print_info(f"Output directory: {Colors.BOLD}{self.mirror_dir}{Colors.END}")
        print_info(f"Using {Colors.BOLD}{self.max_threads}{Colors.END} threads")
        print_info(f"Delay between requests: {Colors.BOLD}{self.delay}s{Colors.END}")
        
        self.stats['start_time'] = time.time()
        
        # Create and start worker threads
        threads = []
        for i in range(self.max_threads):
            thread = threading.Thread(target=self.worker, name=f"Worker-{i+1}")
            thread.daemon = True
            thread.start()
            threads.append(thread)
            print_success(f"Started worker thread {i+1}")
        
        # Start progress monitor in separate thread
        progress_thread = threading.Thread(target=self.show_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # Wait for all URLs to be processed
        self.url_queue.join()
        
        # Wait a bit for threads to finish
        time.sleep(2)
        
        end_time = time.time()
        total_time = end_time - self.stats['start_time']
        
        # Print final statistics
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
        print_success("MIRRORING COMPLETED SUCCESSFULLY!")
        print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
        
        print_info(f"Total time: {Colors.BOLD}{total_time:.2f} seconds{Colors.END}")
        print_info(f"Pages downloaded: {Colors.BOLD}{self.stats['pages_downloaded']}{Colors.END}")
        print_info(f"Resources downloaded: {Colors.BOLD}{self.stats['resources_downloaded']}{Colors.END}")
        print_info(f"Errors encountered: {Colors.BOLD}{self.stats['errors']}{Colors.END}")
        print_info(f"Mirror saved to: {Colors.BOLD}{self.mirror_dir}{Colors.END}")
        
        # Show folder structure
        try:
            total_files = sum(1 for _ in self.mirror_dir.rglob('*') if _.is_file())
            total_size = sum(f.stat().st_size for f in self.mirror_dir.rglob('*') if f.is_file())
            print_info(f"Total files: {Colors.BOLD}{total_files}{Colors.END}")
            print_info(f"Total size: {Colors.BOLD}{total_size/1024/1024:.2f} MB{Colors.END}")
        except:
            pass
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Mirroring completed! Enjoy your offline copy! 🎉{Colors.END}")

def main():
    parser = argparse.ArgumentParser(
        description='🎯 Threaded Website Mirroring Tool - Termux Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.YELLOW}{Colors.BOLD}Examples:{Colors.END}
  {Colors.CYAN}python termux_mirror.py https://example.com{Colors.END}
  {Colors.CYAN}python termux_mirror.py https://example.com -t 20 -v{Colors.END}
  {Colors.CYAN}python termux_mirror.py https://example.com -d 0.5 --no-banner{Colors.END}

{Colors.GREEN}{Colors.BOLD}Features:{Colors.END}
  ✅ Threaded downloading ({Colors.MAGENTA}-t{Colors.END})
  ✅ Recursive mirroring ({Colors.MAGENTA}-m{Colors.END})
  ✅ All resources ({Colors.MAGENTA}-p{Colors.END})
  ✅ HTML extensions ({Colors.MAGENTA}-E{Colors.END})
  ✅ Offline links ({Colors.MAGENTA}-k{Colors.END})
  ✅ Real-time progress
  ✅ Beautiful colors & effects
        """
    )
    
    parser.add_argument('url', help='📡 URL to mirror (e.g., https://example.com)')
    parser.add_argument('-t', '--threads', type=int, default=10, 
                       help=f'🔧 Number of threads (default: {Colors.BOLD}10{Colors.END})')
    parser.add_argument('-d', '--delay', type=float, default=0.1,
                       help=f'⏰ Delay between requests in seconds (default: {Colors.BOLD}0.1{Colors.END})')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='📢 Enable verbose logging')
    parser.add_argument('--no-banner', action='store_true',
                       help='🚫 Skip banner display')
    
    args = parser.parse_args()
    
    if not args.no_banner:
        print_banner()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        print_error("❌ URL must start with http:// or https://")
        sys.exit(1)
    
    try:
        mirror = WebsiteMirror(args.url, args.threads, args.delay)
        mirror.mirror()
    except KeyboardInterrupt:
        print_error("\n🛑 Mirroring interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()