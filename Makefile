PYTHON3="C:\Miniconda3\python.exe"

all:
	$(PYTHON3) tumblr2book.py

clean:
	latexmk -c
	rm -vf temp_posts.txt
	rm -vf posts.tex
	rm -vf main.tex

purge: clean
	rm -vfr pictures/