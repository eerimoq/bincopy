#!/bin/sh
#
# Convert srec / hex examples to TI-Txt format using srec_cat
# which is available in Debian package srecord
#

for in_file in $(ls *.hex)
do 
  out_file=${in_file}.txt
  srec_cat $in_file -intel -o $out_file -titxt && echo "${in_file} -> ${out_file}"
done

for in_file in $(ls *.s19)
do 
  out_file=${in_file}.txt
  srec_cat $in_file -motorola -o $out_file -titxt && echo "${in_file} -> ${out_file}"
done