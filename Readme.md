# Tumblr2Book

Nifty tool to get your favorite tumblr blog with you. It downloads it whole and puts it into epub book.

### Requirements

```
ebooklib
gevent
pytumblr
```

also [7-zip](https://7-zip.org)

### Usage

```
usage: tumblr2book.py [-h] [-p] [-i] BLOG_NAME

Assemble Tumblr blog into epub book. By default we don't download any images.

positional arguments:
  BLOG_NAME   tumblr blog name - what is before '.tumblr.com'

optional arguments:
  -h, --help  show this help message and exit
  -p          download photos
  -i          download inline photos
```
