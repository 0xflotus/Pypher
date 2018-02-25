# Pypher Changelog

## 0.3.3 -- 2/25/2018

### Bugfix

* Fixed division of Pypher objects for Python 3+

### Changed

* The default param name now starts with a dollar sign. And if the manually named param does not start with one, it will be prepended to the name

## 0.3.2 -- 2/23/2018

### Bugfix

* `pypher.builder.Raw` and `pypher.builder.FuncRaw` objects will now adopt bound_params from Pypher and Partial objects

## 0.3.1 -- 2/22/2018

### Hotfix

* The `pypher.builder.Label` class did not add back ticks to the labels.

## 0.3.0 -- 2/22/2018

### Changed

* All labels and properties are now wrapped in back ticks to support labels or properties with spaces and other weird characters. From: "n.name" to "n.`name`"

## 0.2.1 -- 2/21/2018

### Fixed

* A bug where the referenced/right-side operators were not behaving correctly if the right side was not a Pypher object. `99 - p.__field__` would output `p.field - 99` it now outputs `99 - p.field`

## 0.2.0 -- 2/20/2018

### Added

* Support for Partial objects.

## 0.1.1 -- 2/17/2018

### Removed

* `pypher.builder.RElATIONSHIPS['both']` -- this relationship doesn't exist as it was defined.
