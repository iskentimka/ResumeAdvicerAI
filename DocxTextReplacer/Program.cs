using System;
using System.IO;
using System.Collections.Generic;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using Newtonsoft.Json;

namespace DocxTextReplacer
{
    // Represents a replacement mapping in the expected format.
    public class Replacement
    {
        [JsonProperty("old")]
        public string Old { get; set; }
        [JsonProperty("new")]
        public string New { get; set; }
    }

    // Represents the structure of your JSON file.
    public class ReplacementMapping
    {
        [JsonProperty("section")]
        public string Section { get; set; }
        [JsonProperty("extracted")]
        public string Extracted { get; set; }
        [JsonProperty("generated")]
        public string Generated { get; set; }
    }

    class Program
    {
        static void Main(string[] args)
        {
            // For debugging purposes, using fixed file paths.
            string inputDocx = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/resume_test.docx";
            string jsonMappingFile = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/generated_data.json";
            string outputDocx = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/resume_test_modified.docx";

            if (!File.Exists(inputDocx) || !File.Exists(jsonMappingFile))
            {
                Console.WriteLine("Error: Input DOCX file or JSON mapping file not found.");
                return;
            }

            try
            {
                // Read JSON mapping file.
                string jsonText = File.ReadAllText(jsonMappingFile);
                // Deserialize the JSON object into a dictionary.
                Dictionary<string, ReplacementMapping> mappingDict = JsonConvert.DeserializeObject<Dictionary<string, ReplacementMapping>>(jsonText);
                // Convert the dictionary values into a list.
                List<ReplacementMapping> mappingList = new List<ReplacementMapping>(mappingDict.Values);

                // Convert mappingList into a list of Replacement objects.
                List<Replacement> replacements = new List<Replacement>();
                foreach (var mapping in mappingList)
                {
                    if (!string.IsNullOrEmpty(mapping.Extracted) && !string.IsNullOrEmpty(mapping.Generated))
                    {
                        replacements.Add(new Replacement { Old = mapping.Extracted, New = mapping.Generated });
                    }
                    else
                    {
                        //Console.WriteLine("Skipping a mapping because extracted or generated text is null/empty.");
                    }
                }

                //Console.WriteLine("Loaded Replacements:");
                foreach (var rep in replacements)
                {
                    Console.WriteLine($"Old: {rep.Old} | New: {rep.New}");
                }

                // Copy input DOCX to output DOCX (to preserve the original).
                File.Copy(inputDocx, outputDocx, true);

                // Replace text in the DOCX file.
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
            using WordprocessingDocument doc = WordprocessingDocument.Open(docxPath, true);
            {
                string docText = File.ReadAllLines("text.txt");
                using (StreamWriter sw = new StreamWriter(doc.MainDocumentPart.GetStream(FileMode.Create)))
                {
                    sw.Write(docText);
                }
            }
            // var body = doc.MainDocumentPart.Document.Body;
            // var paraElems = body.Elements<Paragraph>();

            // foreach (var paraElem in paraElems)
            // {
            //     foreach (var runElem in paraElem.Elements<Run>())
            //     {
            //         // Concatenate all text from the run.
            //         string allText = string.Empty;
            //         foreach (var textElem in runElem.Elements<Text>())
            //         {
            //             allText += textElem.Text;
            //             allText.Replace(textElem.Text, "Checks");
            //             Console.WriteLine("Iteration text: "+textElem.Text);
            //             textElem.Remove(); // Remove the existing text elements.
            //         }

            //         Console.WriteLine("Iteration over");

            //         // For each replacement mapping, replace occurrences in the concatenated text.
            //         foreach (var replacement in replacements)
            //         {
            //             if (!string.IsNullOrEmpty(replacement.Old) && allText.Contains(replacement.Old))
            //             {
            //                 Console.WriteLine($"Replacing '{replacement.Old}' with '{replacement.New}'");
            //                 allText = allText.Replace(replacement.Old, replacement.New);
            //             }
            //         }

            //         // Append the modified text back as a new Text element.
            //         var newTextElem = new Text() { Text = allText };
            //         runElem.Append(newTextElem);
            //     }
            // }
            
            doc.MainDocumentPart.Document.Save();
        }
    }
}