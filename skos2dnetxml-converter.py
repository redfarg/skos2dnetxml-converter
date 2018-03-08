#!/usr/bin/env python
import click, rdflib, glob, os
from rdflib.namespace import Namespace
from rdflib.plugins.sparql import prepareQuery
import xml.etree.ElementTree as ET
from xml.sax._exceptions import SAXParseException

class NoSkosSchemeException(Exception):
    pass

class InvalidTemplateException(Exception):
    pass

DEFAULT_XML_TEMPLATE = os.path.dirname(os.path.abspath( __file__ )) + '/template.xml'
DEFAULT_NAMESPACE = 'parthenos'


@click.command()
@click.argument('source')
@click.option('--namespace', default=DEFAULT_NAMESPACE, help="Defines namespace for the vocabulary files to be created (default is 'parthenos').")
@click.option('--template', default=DEFAULT_XML_TEMPLATE, help='Specifies an XML file as an output template (default is template.xml in the same dir).')
@click.option('--non-verbose', is_flag=True, help='Flag for disabling verbose console output.')
def convert(source, namespace, template, non_verbose):
    """ Converts SKOS-rdf thesaurus(es) in a file (or files in a directory) into vocabulary XML files with a DNET-required syntax, specified by a template.

        Will only try to convert files ending in .rdf. Output files are named "<Name of Concept Scheme>.xml". 
        First looks for topterms defining different vocabularies in a thesaurus (defined through skos:broaderTransitive).
        If none can be found, all unclassified terms will be combined to a single vocabulary. 
        The template xml needs to be valid and contain all necessary nodes (VOCABULARY_NAME, DATE_OF_CREATION, LAST_UPDATE and TERMS).
    """
    if not os.path.isdir(source):
        if not os.path.isfile(source): 
            click.echo(source + ' is not a valid file or directory.')
    else:
        source = source + '/*.rdf'

    for file in glob.glob(source):
        if not non_verbose:
            click.echo('Converting SKOS file:  ' + file + '\n')

        g=rdflib.Graph()
        try:
            g.load(file)
        except SAXParseException as e:
            click.echo('\nError parsing file (' + file +'): \n' + str(e) + '\nFile will be skipped.\n')
            continue

        try:
            date, thesaurus_name, source_url = find_thesaurus_name_date_and_source_url(g)
        except NoSkosSchemeException:
            click.echo('\nError: No valid SKOS concept scheme found. File ' + file + ' will be skipped.\n')
            continue

        topterms = find_topterms(g, source_url)

        all_terms = {}
        if not (len(topterms)==1 and 'Unclassified terms' in topterms):
            for topterm in topterms:
                if not non_verbose:
                    click.echo('Extracting terms for topterm: ' + topterm) 
                all_terms[str(topterm)] = find_terms_for_topterm(g, topterms[topterm])
        
        if not all_terms:
            all_terms[thesaurus_name] = find_all_terms_in_rdf_graph(g) # case for no existing topterms (except 'Unclassified terms')

        if not non_verbose:
            click.echo() 

        try:
            for vocname in all_terms:
                write_terms_into_xml(all_terms[vocname], template, namespace, vocname, date, non_verbose)
        except InvalidTemplateException as e:
            click.echo('Error parsing the template file ' + template +' : \n' + str(e)+ '\nNo file(s) created.')

    if not non_verbose:
        click.echo('\nDone.')


def find_thesaurus_name_date_and_source_url(rdf_graph):
    """ Tries to find name, creation date and source url of the thesaurus. """
    qres = rdf_graph.query(
            """SELECT ?label ?date ?concept
            WHERE {
            ?concept skos:prefLabel ?label.
            ?concept dc:date ?date.
            ?concept rdf:type skos:ConceptScheme.
            }""",
            initNs=dict(
            skos=Namespace("http://www.w3.org/2004/02/skos/core#"),
            dc=Namespace("http://purl.org/dc/elements/1.1/"))
            )    
    res = list(qres)
    if len(res) < 1:
        raise NoSkosSchemeException
    thesaurus_name = res[0][0].lower()
    date_components = res[0][1].split('_')
    date = date_components[0] + 'T' + ':'.join(date_components[1].split('-')[:3])
    source_url = res[0][2]

    return date, thesaurus_name, source_url


def find_topterms(rdf_graph, source_url):
    """ Tries to find and return all topterms in the rdf graph. """
    source_url = '<' + str(source_url) + '>'

    query = prepareQuery('SELECT ?label ?concept WHERE {?concept skos:topConceptOf ' + source_url + '. ?concept skos:prefLabel ?label. FILTER (LANG(?label) = "en")}',
            initNs=dict(
            skos=Namespace("http://www.w3.org/2004/02/skos/core#")))

    qres = rdf_graph.query(query)

    topterms = {}
    for topterm in qres:
        topterms[str(topterm[0])] = topterm[1]
    return topterms


def find_terms_for_topterm(rdf_graph, topterm):
    """ Tries to find all terms for which a given topterm is a skos:broaderTransitive. """ 
    topterm = '<' + str(topterm) + '>'

    query = prepareQuery(
        'SELECT ?label WHERE { ?concept skos:prefLabel ?label. ?concept rdf:type skos:Concept. ?concept skos:broaderTransitive ' + topterm + '. FILTER (LANG(?label) = "en")}',
            initNs=dict(
            skos=Namespace("http://www.w3.org/2004/02/skos/core#")))

    qres = rdf_graph.query(query)    

    terms = []
    for label in qres:
        terms.append(label[0])
    return terms


def find_all_terms_in_rdf_graph(rdf_graph):
    """ Tries to find all terms (of type skos:Concept) in the rdf graph.

        This is called when no topterms (except 'Unclassified terms') exist, a.e. the 
        thesaurus only contains a single vocabulary without a specified topterm.
     """
    qres = rdf_graph.query(
            """SELECT ?label 
            WHERE { ?concept skos:prefLabel ?label. 
            ?concept rdf:type skos:Concept.
            }""",
            initNs=dict(skos=Namespace("http://www.w3.org/2004/02/skos/core#")))    

    terms = []
    for label in qres:
        terms.append(label[0])

    return terms


def write_terms_into_xml(terms, template, namespace, vocab_name, date, non_verbose):
    """ Writes terms and metadata of a vocab in an XML, based on the template xml. """
    try:
        tree = ET.parse(template)
    except FileNotFoundError:
        raise InvalidTemplateException('\nFileNotFoundError: No template file found with that name.')
    except ET.ParseError as e:
        raise InvalidTemplateException('Error while parsing template tree: \n' + str(e))
    root = tree.getroot()

    vocab_name = vocab_name.replace(' ', '')

    name_node = root.find('.//VOCABULARY_NAME')
    date_node = root.find('.//DATE_OF_CREATION')
    last_update_node = root.find('.//LAST_UPDATE')
    terms_node = root.find('.//TERMS')

    if not all([node != None for node in [name_node, date_node, last_update_node, terms_node]]):
        raise InvalidTemplateException("Template without one or more mandatory nodes. "
                                       "\nMake sure VOCABULARY_NAME, DATE_OF_CREATION, LAST_UPDATE and TERMS are present.")

    name_node.set('code', namespace + ':' + vocab_name)
    name_node.text = vocab_name
    date_node.set('value', date)
    last_update_node.set('value', date)

    for term in terms:
        term_node = ET.SubElement(terms_node, 'TERM', attrib={'code':term, 'encoding':'DNET', 'english_name':term, 'native_name':term})
        ET.SubElement(term_node, "SYNONYMS")
        ET.SubElement(term_node, "RELATIONS")

    tree.write(vocab_name + '.xml', encoding="UTF-8", xml_declaration=True)
    if not non_verbose:
        click.echo('Wrote result in file: ' + vocab_name + '.xml')    


if __name__== '__main__':
    convert()
