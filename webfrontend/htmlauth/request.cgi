#!/usr/bin/perl

use LoxBerry::System;
use LoxBerry::IO;
use LWP::UserAgent;
use XML::Simple;
use MIME::Base64;
use CGI;

$LoxBerry::IO::DEBUG = 1;

my $gip = '192.168.1.123';
my $gport = 80;
my $gurl = "/mux_http";
my $msnr = 1;
my $msudpport = 10000;
my $udpprefix = "Gruenbeck";

my $pcfgfile = "$lbpconfigdir/gruenbeck.cfg";
my $pcfg;
my $dbg = 1;

my %xmlresp;

# Read params from URL
my $cgi = CGI->new;

print STDERR "Start\n" if ($dbg);

read_config();

print STDERR "Config was read\n" if ($dbg);

$msnr = $pcfg->param('Main.msno') if $pcfg->param('Main.msno');
$msudpport = $pcfg->param('Main.msudpport') if $pcfg->param('Main.msudpport');
$gip = $pcfg->param('Main.gip') if $pcfg->param('Main.gip');
$gport = $pcfg->param('Main.gport') if $pcfg->param('Main.gport');
$gcode = $pcfg->param('Main.gcode') if $pcfg->param('Main.gcode');
$useudp = is_enabled($pcfg->param('Main.use_udp'));
$usehttp = is_enabled($pcfg->param('Main.use_http'));

print STDERR "Params initialized\n" if ($dbg);


# Upgrade config version
my $action = uc($cgi->param('action'));

print STDERR "action parameter was read\n" if ($dbg);

if ($action eq "upgrade_config") {
	upgrade_config();
	exit();
}

print STDERR "Params from URL now are read\n" if ($dbg);


# Params from URL overrule params from config
$msnr = $cgi->param('ms') if $cgi->param('ms');
$msudpport = $cgi->param('msport') if $cgi->param('msport');
$gip = $cgi->param('gip') if $cgi->param('gip');
$gport = $cgi->param('gport') if $cgi->param('gport');
$gcode = $cgi->param('code') if $cgi->param('code');
$LoxBerry::IO::mem_sendall = 1 if $cgi->param('force');

$cgi->delete('action', 'ms', 'msport', 'gip', 'gport', 'force', 'code');

my @keywords = $cgi->param;

if ($action eq 'GET' or $action eq 'SHOW') {
	my $query = 'id=666&' . params_get();
	$query = $gcode ? $query . '&code=' . $gcode . '~' : $query . '~';
	my $cont = request_post("http://$gip:$gport$gurl", $query);
	parse_gxml($cont);
	xmlresponse("GET request successful", 200);
	exit;
}
if ($action eq 'SET' or $action eq 'EDIT') {
	# Send values
	params_set();
	# Query edited values
	my $query = 'id=666&' . params_get();
	$query = $gcode ? $query . '&code=' . $gcode . '~' : $query . '~';
	$cont = request_post("http://$gip:$gport$gurl", $query);
	parse_gxml($cont);
	xmlresponse("SET request successful", 200);
	exit;
}

print STDERR "Grünbeck: No valid action parameter in request\n";
xmlresponse("No valid action parameter defined in request", 500);
exit;

sub params_get 
{
	print STDERR "Get Parameters\n" if ($dbg);
	# Build query
	my $qu;
	my $query;
	foreach my $param (@keywords) {
		$qu = $qu . uc($param) . "|";
	}
	$qu = substr($qu, 0, -1) . '~';
	$query = 'show=' . $qu;
	print STDERR "Built query: $query\n" if ($dbg);
	return $query;
}

sub params_set
{
	print STDERR "Set Parameters\n" if ($dbg);
	my $qu;
	# Build query
	foreach my $param (@keywords) {
		# Base64 encoding for several parameters
		$value = param_is_base64($param, scalar $cgi->param($param), 0);
		$qu = 'id=666&edit=' . uc($param) . ">" . $value;
		$qu = $gcode ? $qu . '&code=' . $gcode . '~' : $qu . '~';
		print STDERR "Edit query is $qu\n" if ($dbg);
		my $cont = request_post("http://$gip:$gport$gurl", $qu);
		parse_gxml($cont);
	}
	return;
	
}

sub request_post 
{
	my ($url, $query) = @_;

	my $ua = LWP::UserAgent->new;
	$ua->timeout(5);
	print STDERR "request_post Query: $query\n" if ($dbg);
	my $response = $ua->post($url, Content => $query);
	# my $response = $ua->post($url, Content => 'id=665&show=D_A_1_1|D_A_1_2~');
	if ($response->is_error) {
		print STDERR "Grünbeck: Could not fetch data from $gip\n";
		xmlresponse("Could not fetch data from $gip. " . $response->status_line, 500);
		return undef;
	}
	print STDERR $response->status_line . " " . $response->content . "\n" if ($dbg);
	return $response->content;

}

sub parse_gxml
{
	my ($xmlcontent) = @_;
	
	if (!$xmlcontent) {
		print STDERR "Grünbeck: parse_gxml: Empty response.\n";
		xmlresponse("Empty response from device", 500);
		return undef;
	}
	
	my $xml = XML::Simple::XMLin($xmlcontent);
	if (lc($xml->{code}) ne "ok") {
		print STDERR "Grünbeck: Request seems to have failed\n";
		xmlresponse("POST request has failed (not ok). Content is: $xmlcontent", 500);
		return;
	}
	# use Data::Dumper;
	# print Dumper($xml);
	foreach my $key (keys %{$xml}) {
		$$xml{$key} = param_is_base64($key, $$xml{$key}, 1);
		print STDERR $key . " is " . $$xml{$key} . "\n"  if ($dbg);
	}

	if ($useudp) {
		LoxBerry::IO::msudp_send_mem($msnr, $msudpport, $udpprefix, %{$xml});
	}
	if ($usehttp) {
		LoxBerry::IO::mshttp_send_mem($msnr, %{$xml});
	}
	$xmlresp{'dataset'} = %{$xml};
}

sub param_is_base64
{
	
	# Param $decode: 0 = encode; 1 = decode
	my ($param, $value, $decode) = @_;
	$param = uc($param);
	
	# List of parameters that need to Base64-Encode
	my @encparams = qw/	
		D_Y_8_1_1 
		D_Y_8_1_2 
		D_Y_8_1_3 
		D_Y_8_2
		D_Y_8_4
		D_Y_8_5
		D_Y_8_6
		D_Y_8_7
		D_Y_8_8
		/;
	if (grep( /^$param$/, @encparams )) {
		if ($decode) {
			return decode_base64($value);
		} else {
			return encode_base64($value);
		}
	}
	return $value;
}

sub requires_code
{
	# Unfinished
	# Need to compare @codeparams array with @keywords array for identical elements
	my @codeparams = qw/
		D_A_1_1
		D_A_1_2
		D_A_1_3
		D_A_2_1
		D_A_3_1
		D_A_3_2
		D_A_1_4
		D_A_1_5
		D_A_1_8
		D_A_2_4
		D_A_3_4
		D_A_3_5
		D_A_1_9
		D_A_1_6
		D_K_3
		D_K_4
		D_K_14
		D_K_15
		D_K_16
		D_K_17
		D_K_18
		D_K_19
		D_K_20
		D_K_21
	/;
	

}



sub read_config
{
	
	if (! -e $pcfgfile) {
		$pcfg = new Config::Simple(syntax=>'ini');
		$pcfg->param("Main.ConfigVersion", "1");
		$pcfg->write($pcfgfile) or xmlresponse($pcfgfile . ": " . $pcfg->error(), 500);
		
	}
	$pcfg = new Config::Simple($pcfgfile)or xmlresponse($pcfgfile . ": " . $pcfg->error(), 500);
	$pcfg->autosave(1);
	$pcfg->param("Main.msudpport", 10001) if (! $pcfg->param("Main.msudpport"));
	$pcfg->param("Main.msno", 1) if (! $pcfg->param("Main.msno"));
	
}

sub upgrade_config
{
	if (! -e $pcfgfile) {
		$pcfg = new Config::Simple(syntax=>'ini');
		$pcfg->param("Main.ConfigVersion", "2");
		$pcfg->write($pcfgfile) or xmlresponse($pcfgfile . ": " . $pcfg->error(), 500);
	}
	$pcfg = new Config::Simple($pcfgfile) or xmlresponse($pcfgfile . ": " . $pcfg->error(), 500);
	$pcfg->autosave(1);
	
	# Update configuration
	# V1 -> V2
	if ($pcfg->param("Main.ConfigVersion") < 2){
		$pcfg->param("Main.ConfigVersion", "2");
		$pcfg->param("Main.use_udp", "True");
	}
}

sub xmlresponse
{
	my ($message, $httperr)  = @_;
	if ($httperr >= 400) {
		$xmlresp{'success'} = 'false';
		$xmlresp{'errormessage'} = $message;
		print $cgi->header('text/xml', "$httperr Execution error");
	} else {
		$xmlresp{'success'} = 'true';
		$xmlresp{'successmessage'} = $message;
		print $cgi->header('text/xml', "$httperr OK");
	}
	print XMLout(\%xmlresp);
	
	exit 1 if ($httperr >= 400);
	exit 0;
}

END
{
	my $err = $?;
	if ($xmlresp{'success'} eq "") {
		xmlresponse("Finished without errors", 200) if ($err == 0);
		xmlresponse("Unknown ERROR", 500) if ($err != 0);
	}
}