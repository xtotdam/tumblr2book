#! /usr/bin/python3
# -*- coding: utf-8 -*-

import gevent
from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool, Timeout

from ebooklib import epub
from functools import partial
from math import ceil
from string import Template

import argparse
import os
import pytumblr
import re
import shutil
import sys
import time

from urllib.request import urlopen

from secret import tumblr_api_key
client = pytumblr.TumblrRestClient(tumblr_api_key)

parser = argparse.ArgumentParser(description='Assemble Tumblr blog into epub book. By default we don\'t download any images.')
parser.add_argument('-p', action='store_true', help='download photos')
parser.add_argument('-i', action='store_true', help='download inline photos. Will not work without -p')
parser.add_argument('-r', action='store_true', help='reverse order of posts. Default is from new to old (like Tumblr itself)')
parser.add_argument('blog_name', metavar='BLOG_NAME', help='Tumblr blog name - what is before \'.tumblr.com\'')
args = parser.parse_args()

download_images = args.p
download_inline_images = args.i
reverse_posts = args.r

if not download_images:
    download_inline_images = False

if not download_images:
    di_warning = '<p><b> No images are bundled! </b></p>'
elif not download_inline_images:
    di_warning = '<p><b> No inline images are bundled! </b></p>'
else:
    di_warning = ''


compress_images_too = True
if download_images or download_inline_images:
    if shutil.which('7z') is None:
        compress_images_too = False
        print('I couldn\'t find 7z. You will put images into the book yourself.')


blog_name = args.blog_name
blog_info = client.blog_info(blog_name)

try:
    print('{status} {msg}'.format(**blog_info['meta']))
    if blog_info['meta']['status'] in (401, 404):
        exit()
except KeyError:
    pass


info = blog_info['blog']

info['title'] = info['title'].strip()
info['updated'] = time.ctime(int(info['updated']))
info['pages'] = int(ceil(info['posts'] / 20.))

info['pdirname'] = info['name'] + '_pic_cache'  # pictures cache directory

pdirname = info['pdirname']
try:
    os.mkdir(pdirname)
    os.mkdir(pdirname + os.sep + 'inlines')
except:
    # exception is also thrown if directory already exists
    print('Something happened while creating pic cache folder. Not necessary a problem.')

print('** {} **\n\n{} posts\n{} pages'.format(info['name'], info['posts'], info['pages']))


# start creating book
book = epub.EpubBook()
book.set_title(info['title'])
book.add_author(info['title'])
book.add_author('Tumblr2book')
book.set_language('en')

# general info chapter
introchapter = epub.EpubHtml(file_name='intro.xhtml')
introchapter.content = '''
<h1> {} </h1>
<p> <a href="{}"> {} </a> </p>
<p> {} </p>
<p> {} posts </p>
<p> Blog last updated {} </p>
<p> Scraped {} </p>
{}
'''.format(info['title'], info['url'], info['url'], info['description'], info['posts'], info['updated'], time.ctime(), di_warning)
book.add_item(introchapter)

# introducing templates
template_names = [
    # parts of posts
    'header', 'picture', 'chatphrase',
    # whole posts (8 types)
    'text', 'quote', 'link', 'answer', 'video', 'audio', 'photo', 'chat']

templates = {tn: Template(open('templates' + os.sep + tn + '.tmpl').read()) for tn in template_names}


# prepare posts downloading
poolsize = 4    # too much will result in 429 errors
pages_to_fetch = range(info['pages'])
big_posts_dict = dict()
pages_without_posts = list()
timeoutted_pages = list()

def fetch_posts_page(page):
    print('Getting page #', page + 1, 'of', info['pages'], end='\r')
    sys.stdout.flush()
    try:
        with Timeout(5):
            # it is known that pytumblr sometimes never retrieves anything
            response = client.posts(blog_name, offset=20 * page)
            big_posts_dict[page] = response['posts']
    except KeyError:
        if 'errors' in response.keys():
            # this part should be extended with errors handling
            if response['meta']['status'] == 429:
                # too many requests. we will try again later
                timeoutted_pages.append(page)
            else:
                pass
        else:
            print(page, response)
            big_posts_dict[page] = []
            pages_without_posts.append(page)
    except Timeout:
        timeoutted_pages.append(page)

attempt = 0
while pages_to_fetch:
    pool = Pool(max(poolsize - attempt, 1))     # reduce pool size in case of 429 errors
    pool.map(fetch_posts_page, pages_to_fetch)
    pages_to_fetch = timeoutted_pages[:]
    timeoutted_pages = list()
    if pages_to_fetch:
        print('\nClaiming ' + str(len(pages_to_fetch)) + ' timeoutted pages again')
    attempt += 1

# putting everything into single list
posts = list()
for page in range(info['pages']):
    posts += big_posts_dict[page]
del big_posts_dict

print('\n', len(posts), 'posts got')




if download_images:
    # getting all images' urls
    pictures_links = list()
    for post in posts:
        if post['type'] == 'photo':
            for photo in post['photos']:
                pictures_links.append(photo['original_size']['url'])

    print ('We will download', len(pictures_links), 'pics')

    timeoutted_pics = list()

    def fetch_pic(url, inline=False):
        picname = os.path.basename(url)
        if inline:
            localpic = pdirname + os.sep + 'inlines' + os.sep + picname
        else:
            localpic = pdirname + os.sep + picname

        if not os.path.exists(localpic):
            print('+', end='')
            try:
                with Timeout(15):
                    data = urlopen(url).read()
                    with open(localpic, 'wb') as fp:
                        fp.write(data)
            except Timeout:
                timeoutted_pics.append(url)
            except:
                # no pic? it's ok.
                pass
        else:
            print('-', end='')
        sys.stdout.flush()

    pool = Pool(20)
    while pictures_links:
        pool.map(fetch_pic, pictures_links)
        pictures_links = timeoutted_pics[:]
        timeoutted_pics = list()
        if pictures_links:
            print('\nClaiming' + str(len(pictures_links)) + 'timeoutted pics again')

    print ('\nGot \'em')






chapter_size = 200  # number of posts in a single xhtml file inside epub
# too much is not good for old devices, I've read

current_chapter = ''
chapter_num = 0
real_posts_count = len(posts)
pics_to_download = list()   # inline pics
inline_pic_pattern = re.compile(r'<img.*?src="(.*?)".*?\/>')
ids_for_spine = list()

# reversing posts order if needed
if reverse_posts:
    posts = list(reversed(posts))

# extending posts' list to be evenly divided by `chapter_size`
posts += [{'type':'pass'}] * (chapter_size - (len(posts) % chapter_size) + 1)

for i, post in enumerate(posts):
    post['addinfo'] = ''    # additional info. goes into header part
    # post['pdirname'] = pdirname

    if post['type'] == 'photo':
        parsedphotos = ''
        for photo in post['photos']:
            purl = photo['original_size']['url']
            pn = os.path.basename(purl)

            if download_images:
                photo['src'] = '../' + pdirname + '/' + pn
            else:
                photo['src'] = purl
            photo['originalsrc'] = purl
            parsedphotos += templates['picture'].substitute(**photo)

        post['parsedphotos'] = parsedphotos
        post['title'] = None
        post['addinfo'] = '&mdash; {} picture'.format(len(post['photos']))
        if len(post['photos']) > 1: post['addinfo'] += 's'

    if post['type'] == 'chat':
        dialogue = ''
        for phrase in post['dialogue']:
            dialogue += templates['chatphrase'].substitute(**phrase)
        post['body'] = dialogue     # replacing original body

    if post['type'] == 'answer':
        post['title'] = post['summary']
        if download_inline_images:
            if '<img' in post['answer']:
                for url in inline_pic_pattern.findall(post['answer']):
                    pics_to_download.append(url)
                    post['answer'] = post['answer'].replace(url, '../' + pdirname + '/inlines/' + os.path.basename(url))

    if post['type'] == 'text':
        if download_inline_images:
            if '<img' in post['body']:
                for url in inline_pic_pattern.findall(post['body']):
                    pics_to_download.append(url)
                    post['body'] = post['body'].replace(url, '../' + pdirname + '/inlines/' + os.path.basename(url))

    if post['type'] == 'quote':
        post['title'] = None

    if not post['type'] == 'pass':
        post['postnumber'] = str(i + 1)
        if 'title' in post.keys() and post['title'] is None:
            post['title'] = ''
        post['header'] = templates['header'].substitute(**post)
        processed_post = templates[post['type']].substitute(**post)

        current_chapter += processed_post

    # every `chapter_size` posts
    if not (i + 1) % chapter_size:
        c = epub.EpubHtml(file_name='chap_{:04d}.xhtml'.format(chapter_num))
        c.content = current_chapter
        book.add_item(c)
        ids_for_spine.append(c.id)

        current_chapter = ''
        chapter_num += 1






if download_inline_images:
    fetch_inline_pic = partial(fetch_pic, inline=True)

    print ('We will download', len(pics_to_download), 'inline pics')

    pool = Pool(20)
    timeoutted_pics = list()

    while pics_to_download:
        pool.map(fetch_inline_pic, pics_to_download)
        pics_to_download = timeoutted_pics[:]
        timeoutted_pics = list()
        if pics_to_download:
            print('\nClaiming' + str(len(pics_to_download)) + 'timeoutted pics again')

    print ('\nGot \'em')




# creating table of contents
book.toc = (epub.Link('intro.xhtml', 'General info', 'intro'), )
book.toc += tuple(epub.Link(
    'chap_{:04d}.xhtml'.format(n),
    '{} - {}'.format(n * chapter_size + 1, (n + 1) * chapter_size),
    str(n)) for n in range(len(posts) // chapter_size))

last_chap_link = book.toc[-1]
book.toc = book.toc[:-1]

# fixing last entry's last number
if int(last_chap_link.title.split(' ')[0]) - 1 != real_posts_count:
    book.toc += (epub.Link(
        last_chap_link.href,
        '{} - {}'.format(last_chap_link.title.split(' ')[0], real_posts_count),
        last_chap_link.uid), )

# creating spine and stuff
book.spine = ['nav', introchapter.id] + ids_for_spine

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

# writing into book
bookname = info['name'] + '.epub'
epub.write_epub(bookname, book, {})

# a bit time because it is needed here
time.sleep(2)

# a dirty hack since I didn't manage to add images using ebooklib:)
if download_images or download_inline_images:
    if compress_images_too:
        os.system('7z a -tzip {0} {1}/*'''.format(bookname, pdirname))
        if os.path.exists(bookname + '.tmp'):
            shutil.move(bookname + '.tmp', bookname)
    else:
        print('Now open {} as a zip archive and put {} inside. I warned you:)'.format(bookname, pdirname))
