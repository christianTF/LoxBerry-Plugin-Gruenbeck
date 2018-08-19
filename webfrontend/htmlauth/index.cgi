#!/usr/bin/perl

use LoxBerry::Web;
use CGI;
use warnings;
use strict;

my $pcfgfile = "$lbpconfigdir/gruenbeck.cfg";
my $pcfg;

our $cgi = CGI->new;
$cgi->import_names('R');

read_config();

ajax() if ($R::action eq "change");
form();

exit;




sub form
{

	# Main
	my $maintemplate = HTML::Template->new(
		filename => "$lbptemplatedir/index.html",
		global_vars => 1,
		loop_context_vars => 1,
		die_on_bad_params => 0,
		associate => $pcfg,
	);

	# my %L = LoxBerry::System::readlanguage($maintemplate, "language.ini");

	LoxBerry::Web::lbheader("Grünbeck", "https://www.loxwiki.eu/x/YgMWAQ", "");

	my $mshtml = LoxBerry::Web::mslist_select_html( FORMID => 'msno', SELECTED => $pcfg->param('Main.msno'), DATA_MINI => 0, LABEL => "Miniserver an den gesendet wird" );

	$maintemplate->param('MSHTML', $mshtml);
	
	my %Plang = LoxBerry::System::readlanguage("GruenbeckConfig.ini");
	
	my @gparams = ();
	foreach my $param (sort keys %Plang) {
		my %p;
		$p{'Name'} = substr($param, index($param, '.')+1);
		$p{'LangStr'} = $Plang{$param};
		push @gparams, \%p;
	}
	$maintemplate->param('GParams', \@gparams);
	
	
	print $maintemplate->output;

	LoxBerry::Web::lbfooter();

}

sub read_config
{
	
	if (! -e $pcfgfile) {
		$pcfg = new Config::Simple(syntax=>'ini');
		$pcfg->param("Main.ConfigVersion", "1");
		$pcfg->write($pcfgfile);
		
	}
	$pcfg = new Config::Simple($pcfgfile);
	$pcfg->autosave(1);
	$pcfg->param("Main.msudpport", 10001) if (! $pcfg->param("Main.msudpport"));
	$pcfg->param("Main.msno", 1) if (! $pcfg->param("Main.msno"));

}


##############################################
# Ajax calls
##############################################
sub ajax
{
	$pcfg->param("Main." . $R::key, $R::value);
	print $cgi->header(-type => 'application/json;charset=utf-8', -status => "204 No Content");
	exit;

}
