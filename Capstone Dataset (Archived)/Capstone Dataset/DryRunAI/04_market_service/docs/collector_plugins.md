# Market Collector Plugins

Market collectors are imported through the shared collector registry. Importing a module registers concrete collector classes automatically.

The service discovers modules listed in `collector_plugins`, then requests collectors through `CollectorFactory`.

Collectors must not estimate missing fields or merge prices. Every source record remains its own market record unless it is rejected or detected as a duplicate.

