from html.parser import HTMLParser
import sys

content = open("templates/index.html", encoding="utf-8").read()

class MyParser(HTMLParser):
    tags = []
    def handle_starttag(self, tag, attrs):
        if tag not in ["br", "hr", "input", "img", "meta", "link"]:
            self.tags.append(tag)
    def handle_endtag(self, tag):
        if tag in ["br", "hr", "input", "img", "meta", "link"]:
            return
        if self.tags and self.tags[-1] == tag:
            self.tags.pop()
        else:
            print(f"Mismatched: </{tag}>. Expected: </{self.tags[-1] if self.tags else 'None'}>")

parser = MyParser()
parser.feed(content)
print(f"Unclosed tags: {parser.tags}")
