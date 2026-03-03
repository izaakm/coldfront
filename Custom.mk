SHELL := /bin/bash

.PHONY: exclude
exclude: | .exclude
	@echo ".exclude" >> .exclude
	@echo "coldfront/core/allocation/migrations" >> .exclude
	@echo "coldfront/core/grant/migrations" >> .exclude
	@echo "coldfront/core/publication/migrations" >> .exclude
	@echo "coldfront/core/research_output/migrations" >> .exclude
	@echo "coldfront/core/resource/migrations" >> .exclude

.exclude:
	ln -s .git/info/exclude $(@)
