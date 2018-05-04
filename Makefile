PYTHON3="C:\Miniconda3\python.exe"

all:
	$(PYTHON3) tumblr2book.py
	pandoc -f markdown -t latex temp_posts.txt > posts.tex
	latexmk -pdf -f main.tex

clean:
	latexmk -c
	rm -vf posts.tex
	rm -vf main.tex
	rm -vfr pictures/