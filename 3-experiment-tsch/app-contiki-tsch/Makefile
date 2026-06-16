CONTIKI_PROJECT = node
all: $(CONTIKI_PROJECT)

CONTIKI=../../dependencies/contiki-ng

PLATFORMS_EXCLUDE = sky native

# force Orchestra from command line
MAKE_WITH_ORCHESTRA ?= 0
# force Security from command line
MAKE_WITH_SECURITY ?= 0

MAKE_MAC = MAKE_MAC_TSCH

# Overshadow the stock TSCH slot-operation with the local, modified copy in this
# directory: exclude the original from the auto-collected module sources and
# compile ours instead (resolved via vpath, which searches "." before modules).
MODULES_SOURCES_EXCLUDES += tsch-slot-operation.c
PROJECT_SOURCEFILES += tsch-slot-operation.c

# include $(CONTIKI)/Makefile.dir-variables
# MODULES += $(CONTIKI_NG_SERVICES_DIR)/shell

include $(CONTIKI)/Makefile.include
