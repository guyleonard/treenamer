#!/usr/bin/perl
# Author: Guy Leonard, Copyright MMX/MMXI
# Date: 2011

## To Do List
# Figure out why other formats fail to output
# Sort out file-output in HTML so that if only SVG is output the other files don't show up!
# Enforce detection of nexus files when they are .con or even .nex as they are not automatically
# 

# Import packages
use strict;
use warnings;

use Bio::TreeIO;
use Bio::Tree::Tree;
use Bio::Tree::TreeI;
use CGI qw(:cgi-lib);
use CGI::Carp qw(fatalsToBrowser set_message);
set_message('Please send any errors with a description to g.leonard@nhm.ac.uk');
use Cwd;
use feature qw{ switch };
use File::Basename;
use File::Path;
use IO::String;
use Socket;

# Bunch of GLOBAL Variables
our $VERSION         = '0.6.8.1k';
our $EMPTY           = q{};
our $ID              = $EMPTY;
our $ALLOWED_CHARS   = 'a-zA-Z0-9_.-';
our @ACCESSION_ARRAY = $EMPTY;
our @REF_ARRAY       = $EMPTY;
our @NAME_ARRAY      = $EMPTY;
our $FORMAT          = $EMPTY;
our $TREE_FILE       = $EMPTY;
our $SPECIES_FILE    = $EMPTY;
our $EOL             = $EMPTY;

# END OF LINE DECLARATIONS
our $CR   = "\015";        # 0 - Apple II family, Mac OS thru version 9
our $CRLF = "\015\012";    # 1 - CP/M, MP/M, DOS, Microsoft Windows
our $LF   = "\012";        # 2 - Unix, Linux, Xenix, Mac OS X, BeOS, Amiga
our $FF   = "\014";        # 3 - printer form feed

### User Editable Values
our $UPLOAD_DIR = '/var/www';
$CGI::POST_MAX = 1024 * 51200;    # Max Upload (1024 * 51200 = 50MB)

# Generate ID
&ID;

# Assign new CGI query
our $QUERY = CGI->new;

# Upload REFGEN-taxa file
$SPECIES_FILE = &upload_species();

# Upload TREE file
$TREE_FILE = &upload_tree;

# Clean up and outputs
&tidy_dir;

&usage;
&process_form;

sub usage {

    my $user_IP      = $ENV{REMOTE_ADDR};
    my $user_browser = $ENV{HTTP_USER_AGENT};
    my $time         = localtime time;

    my $iaddr = inet_aton("$user_IP");
    my $dns_name = gethostbyaddr( $iaddr, AF_INET );

    open my $usage_out, '>>', "$UPLOAD_DIR\/results\/usage\/treefix.txt"
        or die("Error: Unable to open usage file treefix.txt: $!\n");

    my $usage_output = "$time\t$user_IP\t$dns_name\t$VERSION\t$user_browser\n";

    print $usage_out $usage_output;
    close($usage_out);
}

# Assign a unique session ID to each run
sub ID {

    # Get current time - used as unique identifier
    $ID = time();
    mkdir( "$UPLOAD_DIR\/results\/tf\/$ID", 0755 )
        or die "Cannot create directory: $UPLOAD_DIR\/results\/tf\/$ID\n $!";
    return $ID;
}

sub upload_species {

    my $species_file = $QUERY->param("species_file");

    die( $QUERY->header() . "You may have forgotten to select a taxa file." )
        if !$species_file;

    my ( $species_filen, $species_dir, $species_ext ) = fileparse( $species_file, qr'\..*' );

    # Check for tainting and convert any spaces to underscores "_"
    $species_filen =~ tr/ /_/;
    $species_ext   =~ tr/ /_/;

    # Remove illegal characters
    $species_filen =~ s/[^$ALLOWED_CHARS]//g;
    $species_ext   =~ s/[^$ALLOWED_CHARS]//g;
    if ( $species_filen =~ /^([$ALLOWED_CHARS]+)$/ ) {
        $species_filen = $1;
    }
    else {
        die("The filename is not valid. Filenames can only contain these characters: $ALLOWED_CHARS\n");
    }

    my $species_filename = "$species_filen$species_ext";

    # This file is restricted to CSV or plain TXT - it has no business being anything else.
    if ( $species_ext eq ".csv" or $species_ext eq ".txt" ) {

        # Print the contents of the uploaded file
        open my $upload_species, '>', "$UPLOAD_DIR\/results\/tf\/$ID\/$species_filename"
            or die("Error: Unable to open taxa list file $species_filename: $!\n");
        binmode $upload_species;
        my $upload_filehandle = $QUERY->upload("species_file");

        # Print the contents of the uploaded file
        while (<$upload_filehandle>) {
            s/>/$CR>/gs;
            s/($CR?$LF|$CR)/\n/gs;
            print $upload_species $_;
        }
        close($upload_species);

        # "Accession, REFGEN ID, Taxa" to array
        &file2array("$species_filename");
    }
    else {
        die("File type(extension) must be CSV, please try again.\n");
    }

    return "$species_filename";
}

sub upload_tree {

    my $tree_file = $QUERY->param("tree_file");

    die( $QUERY->header() . "You may have forgotten to select a tree file." )
        if !$tree_file;

    my ( $tree_filen, $tree_dir, $tree_ext ) = fileparse( $tree_file, qr'\..*' );

    # Check for tainting and convert any spaces to underscores "_"
    $tree_filen =~ tr/ /_/;
    $tree_ext   =~ tr/ /_/;

    # Remove illegal characters
    $tree_filen =~ s/[^$ALLOWED_CHARS]//g;
    $tree_ext   =~ s/[^$ALLOWED_CHARS]//g;
    if ( $tree_filen =~ /^([$ALLOWED_CHARS]+)$/ ) {
        $tree_filen = $1;
    }
    else {
        die("The filename is not valid. Filenames can only contain these characters: $ALLOWED_CHARS\n");
    }
    my $tree_filename = "$tree_filen$tree_ext";

    # Print the contents of the uploaded file
    open my $upload_tree, '>', "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_filename"
        or die("Error: Unable to open taxa list file $tree_filename: $!\n");
    binmode $upload_tree;
    my $upload_filehandle = $QUERY->upload("tree_file");

    # Print the contents of the uploaded file to the server
    while (<$upload_filehandle>) {
        s/>/$CR>/gs;
        s/($CR?$LF|$CR)/\n/gs;
        print $upload_tree $_;
    }
    close($upload_tree);

    # Since I am now implementing Bio::Perl modules I need to handle plain SVG input as an exception
    # as it does not read in svggraph - this will also require a non-standard output method too. le sigh
    if ( $tree_ext eq ".svg" ) {
        &svg("$tree_filename");
    }
    else {
        &bioperl_it_up("$tree_filename");
    }

    return "$tree_filename";
}

## Read file to Array ##
sub file2array {

    my $species_filename = shift;

    open my $in, '<', "$UPLOAD_DIR\/results\/tf\/$ID\/$species_filename"
        or die("Error in array2file: Unable to open file: $species_filename: $!\n");

    while (<$in>) {
        chomp;
        my ($line) = $_;
        my @temp = split( /,/, $line );
        $temp[1] =~ s/^ *//g;
        $temp[1] =~ s/ *$//g;
        push( @ACCESSION_ARRAY, $temp[0] );
        push( @REF_ARRAY,       $temp[1] );
        push( @NAME_ARRAY,      $temp[2] );
    }
    close($in);
}

# Okay, I am going to try and read in tree files with Bio::Tree 
# as it allows for many more file types!!
# and headaches too
sub bioperl_it_up {

    my $tree_filename = shift;
    my $input;

    my ( $tree_file_out, $tree_dir_out, $tree_ext_out ) = fileparse( "$tree_filename", qr'\..*' );
   
    # Here we are explicitly detecting nexus files by extension - not perfect but for an unknown reason
    # the bioperl autodetect won't detect MrBayes consensus files in nexus format and throws and error
    # but if we force it to be nexus then it will be read! Hmmm.
    if ($tree_ext_out eq ".con" or $tree_ext_out eq ".nex" or $tree_ext_out eq ".nexus" or $tree_ext_out eq ".nxs") {
    $input = Bio::TreeIO->new( -file => "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_filename", -format => "nexus" );  
    }
    # Why not do it for a few more and fall back on to the autodetect as a last resort!?
    #elsif ($tree_ext_out eq ".fa" or $tree_ext_out eq ".fas" or $tree_ext_out eq ".fasta" or $tree_ext_out eq "fna" or $tree_ext_out eq ".faa" or $tree_ext_out eq ".fst") {
    #   $input = Bio::TreeIO->new( -file => "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_filename", -format => "newick" ); 
    #}
    else {
        $input = Bio::TreeIO->new( -file => "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_filename" );
    }

    my $tree = $input->next_tree;

    my $label = $QUERY->param("label");
    my $block = $QUERY->param("block");
    given ($label) {
        when ('acc') {
            for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                    my $refgen_id    = $REF_ARRAY[$i];
                    my $current_node = $node->id;
                    if ( $current_node eq $refgen_id ) {
                        $node->id("$ACCESSION_ARRAY[$i]");
                    }
                }
            }
        }
        when ('tax') {
            given ($block) {
                when ('full') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id    = $REF_ARRAY[$i];
                            my $current_node = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$NAME_ARRAY[$i]");
                            }
                        }
                    }
                }
                when ('short') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id     = $REF_ARRAY[$i];
                            my $taxon         = $NAME_ARRAY[$i];
                            my @genus_species = split( / /, $taxon );
                            my $genus         = substr $genus_species[0], 0, 1;
                            $genus = "$genus.";
                            my $replace      = "$genus$genus_species[1]";
                            my $current_node = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$replace");
                            }
                        }
                    }
                }
                when ('tiny') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id     = $REF_ARRAY[$i];
                            my $taxon         = $NAME_ARRAY[$i];
                            my @genus_species = split( / /, $taxon );
                            my $genus         = substr $genus_species[0], 0, 1;
                            my $species       = substr $genus_species[1], 0, 1;
                            my $replace       = "$genus$species";
                            my $current_node  = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$replace");
                            }
                        }
                    }
                }
            }
        }
        when ('both') {
            given ($block) {
                when ('full') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id    = $REF_ARRAY[$i];
                            my $current_node = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$NAME_ARRAY[$i]\_\[$ACCESSION_ARRAY[$i]\]");
                            }
                        }
                    }
                }
                when ('short') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id     = $REF_ARRAY[$i];
                            my $taxon         = $NAME_ARRAY[$i];
                            my @genus_species = split( / /, $taxon );
                            my $genus         = substr $genus_species[0], 0, 1;
                            $genus = "$genus.";
                            my $replace      = "$genus$genus_species[1]";
                            my $current_node = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$replace\_\[$ACCESSION_ARRAY[$i]\]");
                            }
                        }
                    }
                }
                when ('tiny') {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id     = $REF_ARRAY[$i];
                            my $taxon         = $NAME_ARRAY[$i];
                            my @genus_species = split( / /, $taxon );
                            my $genus         = substr $genus_species[0], 0, 1;
                            my $species       = substr $genus_species[1], 0, 1;
                            my $replace       = "$genus$species";
                            my $current_node  = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$replace\_\[$ACCESSION_ARRAY[$i]\]");
                            }
                        }
                    }
                }
                default {
                    for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
                        for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
                            my $refgen_id    = $REF_ARRAY[$i];
                            my $current_node = $node->id;
                            if ( $current_node eq $refgen_id ) {
                                $node->id("$NAME_ARRAY[$i]\_\[$ACCESSION_ARRAY[$i]\]");
                            }
                        }
                    }
                }
            }
        }
    }

    # This method steps through each leaf node (by refgen id) and compares it to the species list
    # and replaces it with the correctly matched taxon and accession number whilst keeping the
    # tree data structure intact so that I can output via Bio::TreeIO
    # it took over a day to figure this out! Whilst it was "one of those days" Bio::Perl docs did not help
    #
    #for my $node ( grep { $_->is_Leaf } $tree->get_nodes ) {
    #    for ( my $i; $i <= $#REF_ARRAY; $i++ ) {
    #        my $refgen_id    = $REF_ARRAY[$i];
    #        my $current_node = $node->id;
    #        if ( $current_node eq $refgen_id ) {
    #            $node->id("$NAME_ARRAY[$i]\_\[$ACCESSION_ARRAY[$i]\]");
    #        }
    #    }
    #}

    my $out_0 = Bio::TreeIO->new(
        -format => 'newick',
        -file   => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.tree"
    );
    $out_0->write_tree($tree);
    my $out_1 = Bio::TreeIO->new(
        -format => 'nexus',
        -file   => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.nex"
    );
    $out_1->write_tree($tree);
    my $out_2 = Bio::TreeIO->new(
        -format => 'nhx',
        -file   => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.nhx"
    );
    $out_2->write_tree($tree);
    my $out_3 = Bio::TreeIO->new(
        -format => 'tabtree',
        -file   => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.tab"
    );
    $out_3->write_tree($tree);

## Bio::Perl, on my machines, seems to have problems with these formats at the moment...
#
    #my $out = Bio::TreeIO->new(-format => 'phyloxml',-file   => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.xml");
    #$out->write_tree($tree);
    #my $out = Bio::TreeIO->new(-format => 'svggraph',-file => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.svg");
    #$out->write_tree($tree);
    #my $out = Bio::TreeIO->new(-format => 'pag', -file => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.pag");
    #$out->write_tree($tree);
    #my $out = Bio::TreeIO->new(-format => 'nexml', -file => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.nexml");
    #$out->write_tree($tree);
    #my $out = Bio::TreeIO->new(-format => 'lintree', -file => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.lin");
    #$out->write_tree($tree);
    #my $out = Bio::TreeIO->new(-format => 'cluster', -file => ">$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out.clu");
    #$out->write_tree($tree);

}

sub svg {

    my $tree_filename = shift;

    open my $in, '<', "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_filename\_edit"
        or die("Error in conversion SVG: Unable to open file: $tree_filename\_edit: $!\n");

    my ( $tree_file_out, $tree_dir_out, $tree_ext_out ) = fileparse( "$tree_filename", qr"\..*" );

    open my $svg_out, '>', "$UPLOAD_DIR\/results\/tf\/$ID\/$tree_file_out\_fixed$tree_ext_out\_edit"
        or die("Error: Unable to write svg file $tree_file_out\_fixed$tree_ext_out\_edit: $!\n");
    while (<$in>) {
        my $line  = $_;
        my $label = $QUERY->param("label");
        my $block = $QUERY->param("block");
        given ($label) {
            when ('both') {
                given ($block) {
                    when ('full') {
                        for ( my $i = 0; $i <= $#REF_ARRAY; $i++ ) {
                            my $ref = "$REF_ARRAY[$i]";
                            my $rep = "$NAME_ARRAY[$i]\_\[$ACCESSION_ARRAY[$i]\]";
                            $line =~ s/$ref/$rep/gi;
                            $line =~ s/\n//g;
                        }
                        print $svg_out "$line";
                    }
                    when ('short') {
                        for ( my $i = 0; $i <= $#REF_ARRAY; $i++ ) {
                            my $ref     = "$REF_ARRAY[$i]";
                            my $rep     = "$NAME_ARRAY[$i]";
                            my @genspec = split( / /, $rep );
                            my $genus   = substr $genspec[0], 0, 1;
                            $genus = "$genus.";
                            my $species = $genspec[1];
                            $rep = "$genus$species\_\[$ACCESSION_ARRAY[$i]\]";
                            $line =~ s/$ref/$rep/gi;
                            $line =~ s/\n//g;
                        }
                        print $svg_out "$line";
                    }
                    when ('tiny') {
                        for ( my $i = 0; $i <= $#REF_ARRAY; $i++ ) {
                            my $ref     = "$REF_ARRAY[$i]";
                            my $rep     = "$NAME_ARRAY[$i]";
                            my @genspec = split( / /, $rep );
                            my $genus   = substr $genspec[0], 0, 1;
                            my $species = substr $genspec[1], 0, 1;
                            $rep = "$genus$species\_\[$ACCESSION_ARRAY[$i]\]";
                            $line =~ s/$ref/$rep/gi;
                            $line =~ s/\n//g;
                        }
                        print $svg_out "$line";
                    }
                }
            }
        }
    }
    close($svg_out);
    close($in);

}

sub tidy_dir {

    # Clear up old file results
    my $time_now = time();
    my $d        = "$UPLOAD_DIR\/results\/tf";
    opendir( DIR, $d ) || die "can't opendir $d: $!";
    my @dirs = grep { !/^\./ && -d "$d/$_" } readdir(DIR);
    closedir DIR;
    for ( my $i = 0; $i <= $#dirs; $i++ ) {
        my $diff = $time_now - $dirs[$i];

        # Delete after a week (in seconds)
        if ( $diff >= 604800 ) {
            rmtree( "$d\/$dirs[$i]", 0, 0 );
        }
    }
}

sub html_out {

    open my $html_out, '>', "$UPLOAD_DIR\/results\/tf\/$ID\/$ID.html"
        or die("Error: Unable to open file $ID.html: $!\n");

    my ( $file_name, $file_dir, $file_ext ) = fileparse( $TREE_FILE, qr"\..*" );

    print $html_out <<"ENDOFTEXT";
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>TREENAMER Results</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/treenamer/css/refgen.css" />
</head>

<body>
    <div class=\"title\">
        <span class=\"ref\">TREE</span><span class=\"gen\">NAMER</span>
        <img src=\"/treenamer/css/treenamer_title.png\" class=\"title\" alt=\"TREENAMER Logo\" />
        <span class= \"subtitle\">TREENAMER - Rename REFGEN IDs in your Trees</span>
    </div>
    <div class="container">
            <form  id="form1" name="form1">
    <fieldset>
        <legend>TREENAMER ID</legend>
                <h1><span></span>$ID</h1>
                <p>Please bookmark <a href="/results/tf/$ID/$ID.html">this</a> URL if you wish to review your results at another time.<br /><br />
                Your results will be stored and available for around one week.</p>
        </fieldset>

    <fieldset>
                <legend>Original Files</legend>
                <ol>
                <li><a href="/results/tf/$ID/$SPECIES_FILE">$SPECIES_FILE</a></li>
                <li><a href="/results/tf/$ID/$TREE_FILE\_edit">$TREE_FILE</a></li>
                </ol>
        </fieldset>

        <fieldset>
                <legend>TREENAMER Files</legend>
                <ol>
        <li>Newick: <a href="/results/tf/$ID/$file_name\.tree">$file_name\.tree</a></li>
        <li>eXtended Newick: <a href="/results/tf/$ID/$file_name\.nhx">$file_name\.nhx</a></li>
                <li>Nexus: <a href="/results/tf/$ID/$file_name\.nex">$file_name\.nex</a></li>
        <li>Tab Tree: <a href="/results/tf/$ID/$file_name\.tab">$file_name\.tab</a></li>
        <li>Phyloxml: <a href="/results/tf/$ID/$file_name\.xml">$file_name\.xml</a></li>
                </ol>
        </fieldset>

        <fieldset>
                <legend>Information</legend>
                <ol>
                        <li>Thank you for using TREENAMER $VERSION</li><li>&nbsp;</li>
                        <li>Please come back again and don't forget to suggest these tools to your friends!</li>
            <li>&nbsp;</li><li>Citation: <a href=
        "http://www.la-press.com/refgen-and-treenamer-automated-sequence-data-handling-for-phylogenetic-a1451">
        Leonard, G., et al. (2009). REFGEN and TREENAMER: Automated Sequence Data Handling for
        Phylogenetic Analysis in the Genomic Era. <em>Evolutionary Bioinformatics Online</em>,
        5:1-4.</a></li><li>&nbsp;</li>
                </ol>
        </fieldset>
        </form>
</div>
</body>
</html>
ENDOFTEXT
    print &HtmlBot;
}

# Redirect HTML Header
sub redirect_head {
    return <<"END_OF_TEXT";
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
  <title>Your TREENAMER Results are being generated...</title>
  <META HTTP-EQUIV="Refresh" CONTENT="2; URL=/results/tf/$ID/$ID.html">
  <link rel="stylesheet" type="text/css" media="screen" href="../treenamer/css/refgen.css" />
</head>
END_OF_TEXT
}

sub process_form {
    print &PrintHeader;
    print &redirect_head;

    print <<"ENDOFTEXT";


<body>
    <div class=\"title\">
        <span class=\"ref\">TREE</span><span class=\"gen\">NAMER</span>
        <img src=\"/treenamer/css/treenamer_title.png\" class=\"title\" alt=\"TREENAMER Logo\" />
        <span class= \"subtitle\">TREENAMER - Rename REFGEN IDs in your Trees</span>
    </div>
    <div class="container">
            <form  id="form1" name="form1">
    <fieldset>
        <legend>Generating Results</legend>
                <h1><span></span>$ID</h1>
                <p>Working...</p>
        <p>Treenamer Version: $VERSION</p>
        </fieldset>
    </form>
    </div>
</body>
ENDOFTEXT
    print &HtmlBot;
    &html_out;
}