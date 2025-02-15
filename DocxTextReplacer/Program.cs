
using System;
using System.IO;
using System.Linq;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using Newtonsoft.Json;
using System.Collections.Generic;

class Program
{
    static void Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.WriteLine("Usage: DocxTextReplacer <input_docx> <json_mapping> <output_docx>");
            return;
        }

        string inputDocx = args[0];
        string jsonMappingFile = args[1];
        string outputDocx = args[2];

        if (!File.Exists(inputDocx) || !File.Exists(jsonMappingFile))
        {
            Console.WriteLine("Error: Input DOCX file or JSON mapping file not found.");
            return;
        }

        try
        {
            // Read JSON mapping file
            string jsonText = File.ReadAllText(jsonMappingFile);
            var replacements = JsonConvert.DeserializeObject<List<Replacement>>(jsonText);

            // Copy the input DOCX file to the output location
            File.Copy(inputDocx, outputDocx, true);

            // Perform text replacement
            ReplaceTextInDocx(outputDocx, replacements);

            Console.WriteLine("Text replacement completed successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }

    static void ReplaceTextInDocx(string docxPath, List<Replacement> replacements)
    {
        using (WordprocessingDocument doc = WordprocessingDocument.Open(docxPath, true))
        {
            var body = doc.MainDocumentPart.Document.Body;
            foreach (var replacement in replacements)
            {
                foreach (var text in body.Descendants<Text>())
                {
                    if (text.Text.Contains(replacement.Old))
                    {
                        text.Text = text.Text.Replace(replacement.Old, replacement.New);
                    }
                }
            }
            doc.Save();
        }
    }

    class Replacement
    {
        public string Old { get; set; }
        public string New { get; set; }
    }
}