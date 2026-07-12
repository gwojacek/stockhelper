.PHONY: build install-stock help allsearch open-allsearch chart ichimoku fibo journal journal-pdf cleanup fix-permissions cache-only force-fibo wig-bulk trim-wig

TARGET ?= ena
MARKET ?= wig
SYMBOL ?= MPWR.US

build:
	docker compose build

install-stock:
	./scripts/install-stock-command.sh

help:
	./stock --help

allsearch:
	./stock -allsearch all

open-allsearch:
	./stock --open-allsearch-report all

chart:
	./stock -c $(TARGET)

ichimoku:
	./stock -ichimoku_search $(MARKET)

fibo:
	./stock -fibo_search $(MARKET)

journal:
	./stock --journal-html

journal-pdf:
	./stock --journal-pdf

cache-only:
	./stock -onlycache -ichimoku_search $(MARKET)

force-fibo:
	STOCKHELPER_FORCE_REMOTE_REFRESH=1 ./stock -fibo_search $(MARKET)

wig-bulk:
	./stock --download-wig-bulk

trim-wig:
	./stock --trim-wig-csvs

cleanup:
	./stock --cleanup

fix-permissions:
	./stock --fix-permissions
