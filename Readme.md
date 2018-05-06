# Tumblr2Book

A nifty tool that lets you read your favorite tumblr blog offline.  It downloads all the posts and puts them into an epub book you can enjoy everywhere.

Don't forget to put your API key into `secret.py` into `tumblr_api_key` variable.

### Requirements

```
ebooklib
gevent
pytumblr
```

also [7-zip](https://7-zip.org)

### Usage

```
usage: tumblr2book.py [-h] [-p] [-i] [-r] BLOG_NAME

Assemble Tumblr blog into epub book. By default we don't download any images.

positional arguments:
  BLOG_NAME   Tumblr blog name - what is before '.tumblr.com'

optional arguments:
  -h, --help  show this help message and exit
  -p          download photos
  -i          download inline photos. Will not work without -p
  -r          reverse order of posts. Default is from new to old (like Tumblr itself)
```
