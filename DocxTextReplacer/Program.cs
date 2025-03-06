using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using Newtonsoft.Json;

namespace DocxTextReplacer
{
    public class Replacement
    {
        public string? Old { get; set; }
        public string? New { get; set; }
    }

    public class ReplacementMapping
    {
        public string? Section { get; set; }
        public string? Extracted { get; set; }
        public string? Generated { get; set; }
    }

    class Program
    {
        static void Main(string[] args)
        {
            // Example hard-coded paths:
            string inputDocx = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/resume_test.docx";
            string jsonMappingFile = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/generated_data.json";
            string outputDocx = "/Users/edzhisk/Desktop/Projects/ResumeAdvicerAI/backend/resume_test_modified.docx";

            if (!File.Exists(inputDocx) || !File.Exists(jsonMappingFile))
            {
                Console.WriteLine("Error: Input DOCX or JSON file not found.");
                return;
            }

            try
            {
                // 1. Read JSON mapping
                string jsonText = File.ReadAllText(jsonMappingFile);
                var mappingDict = JsonConvert.DeserializeObject<Dictionary<string, ReplacementMapping>>(jsonText)
                                  ?? new Dictionary<string, ReplacementMapping>();

                // 2. Build replacements
                var replacements = new List<Replacement>();
                foreach (var kvp in mappingDict)
                {
                    var map = kvp.Value;
                    if (!string.IsNullOrEmpty(map.Extracted) && !string.IsNullOrEmpty(map.Generated))
                    {
                        replacements.Add(new Replacement
                        {
                            Old = map.Extracted,
                            New = map.Generated
                        });
                    }
                }

                Console.WriteLine("----- Loaded Replacements -----");
                foreach (var r in replacements)
                {
                    Console.WriteLine($"Old: {r.Old}\nNew: {r.New}\n");
                }
                Console.WriteLine("--------------------------------");

                // 3. Copy the docx
                File.Copy(inputDocx, outputDocx, overwrite: true);

                // 4. Run the merging replacer
                ReplaceTextInDocx(outputDocx, replacements);

                Console.WriteLine("Text replacement completed successfully.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        /// <summary>
        /// Merges consecutive runs that share the same style, does in-run 
        /// replacements for each merged block, then re-inserts them into the paragraph. 
        /// This preserves styling for each block while allowing multi-run strings 
        /// in the same style to be replaced.
        /// </summary>
        static void ReplaceTextInDocx(string docxPath, List<Replacement> replacements)
        {
            using var doc = WordprocessingDocument.Open(docxPath, true);
            var body = doc.MainDocumentPart.Document.Body;
            if (body == null)
            {
                Console.WriteLine("Document has no body.");
                return;
            }

            var paragraphs = body.Elements<Paragraph>().ToList();

            foreach (var paragraph in paragraphs)
            {
                var runs = paragraph.Elements<Run>().ToList();
                if (!runs.Any()) continue;


                // We'll build a new list of runs to replace the old ones
                var newRunsList = new List<Run>();

                // A temporary buffer for merging consecutive same-style runs
                Run? currentMergedRun = null;
                string currentMergedText = "";

                // Helper to flush the currentMergedRun+Text to newRunsList
                void FlushCurrentRun()
                {
                    if (currentMergedRun == null) return; // nothing to flush
                    // We do the replacements in currentMergedText
                    foreach (var rep in replacements)
                    {
                        if (!string.IsNullOrEmpty(rep.Old) && !string.IsNullOrEmpty(rep.New))
                        {
                            if (currentMergedText.Contains(rep.Old))
                            {
                                currentMergedText = currentMergedText.Replace(rep.Old, rep.New);
                            }
                        }
                    }
                    // Set the merged text
                    var textElem = new Text(currentMergedText);
                    // Clear existing text elements from the run
                    currentMergedRun.RemoveAllChildren<Text>();
                    // Append our new text element
                    currentMergedRun.Append(textElem);

                    // Add the run to the final list
                    newRunsList.Add(currentMergedRun);
                    currentMergedRun = null;
                    currentMergedText = "";
                }

                // Compare run styles
                bool HaveSameStyle(Run r1, Run r2)
                {
                    // If both have null or empty RunProperties, treat them as same style
                    // or compare runProperties XML if needed for a stricter approach
                    var rp1 = r1.RunProperties?.OuterXml ?? "";
                    var rp2 = r2.RunProperties?.OuterXml ?? "";
                    return rp1 == rp2;
                }

                // Main loop: Merge consecutive runs if style is identical
                foreach (var run in runs)
                {
                    if (currentMergedRun == null)
                    {
                        // Start a new merged run buffer
                        currentMergedRun = (Run)run.CloneNode(true);
                        // We'll clear the text from the cloned run and store it in currentMergedText
                        var textParts = currentMergedRun.Elements<Text>().Select(t => t.Text).ToList();
                        currentMergedText = string.Join("", textParts);
                        // remove all old text child nodes
                        currentMergedRun.RemoveAllChildren<Text>();
                    }
                    else
                    {
                        // Check if style matches
                        if (HaveSameStyle(currentMergedRun, run))
                        {
                            // If same style, we unify text
                            var textParts = run.Elements<Text>().Select(t => t.Text).ToList();
                            var combined = string.Join("", textParts);
                            currentMergedText += combined;
                        }
                        else
                        {
                            // Different style => flush what we have, then start a new buffer
                            FlushCurrentRun();

                            currentMergedRun = (Run)run.CloneNode(true);
                            var textParts = currentMergedRun.Elements<Text>().Select(t => t.Text).ToList();
                            currentMergedText = string.Join("", textParts);
                            currentMergedRun.RemoveAllChildren<Text>();
                        }
                    }
                }
                // End of runs => flush the last buffer
                FlushCurrentRun();

                // Now we remove all old runs from the paragraph
                foreach (var r in runs) {
                    string runText = string.Join("", r.Elements<Text>().Select(t => t.Text));
                    Console.WriteLine(runText);
                    Console.WriteLine("run");
                }
                // And append our newRunsList
                foreach (var newRun in newRunsList)
                {
                    paragraph.Append(newRun);
                }
                Console.WriteLine("paragraph");
            }

            doc.MainDocumentPart.Document.Save();
        }
    }
}