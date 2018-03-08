# skos2dnetxml-converter
Command line python script that converts SKOS-rdf thesaurus(es) in a file (or files in a directory) into vocabulary XML files with a DNET-required syntax, specified by a template.

## Details
The script first looks for top terms/concepts defining different vocabularies in a thesaurus (defined through skos:broaderTransitive). If none can be found, all unclassified terms will be combined to a single vocabulary. The template xml needs to be valid and contain all necessary nodes (*VOCABULARY_NAME*, *DATE_OF_CREATION*, *LAST_UPDATE* and *TERMS*).

## Setup
Please note that this was written for Python 3.5+. As of right now, I can't guarantee it running on lower versions.

For installing the requirements:  `pip install -r requirements.txt` 
(I'd recommend using a virtual env)

## Usage

```
python skos2dnetxml-converter.py [OPTIONS] SOURCE 
```
`SOURCE` must specifiy a .rdf file or a directory (for which only .rdf files will be considered). Output files are named "<Name of Concept Scheme>.xml".

**Options:**

`--namespace TEXT`  Defines namespace for the vocabulary files to be created (default is 'parthenos').

`--template TEXT`   Specifies an XML file as an output template (default is template.xml in the same dir).

`--non-verbose`     Flag for disabling verbose console output.

`--help`            Display help message and exit.
