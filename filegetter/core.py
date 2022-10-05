#!/usr/bin/env python
# -*- coding: utf8 -*-
import click
import logging
from pprint import pprint

from .cmds.project import FilegetterBuilder

# logging.getLogger().addHandler(logging.StreamHandler())
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)


def enableVerbose():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG)




@click.group()
def cli1():
    pass


@cli1.command()
@click.argument('mode', default="full")
@click.option('--projectpath', '-p', default=None, help='Project path')
@click.option('--verbose', '-v', count=False, help='Verbose output. Print additional info')
def run(mode, projectpath, verbose):
    """Executes project, collects data from API"""
    if verbose:
        enableVerbose()
    if projectpath:
        acmd = FilegetterBuilder(projectpath)
    else:
        acmd = FilegetterBuilder(projectpath)
    acmd.run(mode)
    pass


@click.group()
def cli4():
    pass

cli = click.CommandCollection(sources=[cli1])

# if __name__ == '__main__':
#    cli()
