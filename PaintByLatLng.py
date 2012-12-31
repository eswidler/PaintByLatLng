import webapp2
import codecs
import os, urllib, json, cgi, logging, unicodedata
from google.appengine.ext.webapp import template

class BaseHandler(webapp2.RequestHandler):
    """Functions common to all handlers"""
    @property
    def db(self):
        return db
        
    @property
    def base_uri(self):
        """Returns the Web service's base URI (e.g., http://localhost:8888)"""
        """logging.info("results " + str(self.request))"""
        return self.request.get('Referer')
    
    def get_format(self):
        #returns format for redirect from accept header
        mappings= {"text/html":".html","application/json":".json","application/xml":".xml","text/turtle":".ttl"}
        accept= self.request.headers.get('Accept')
        if accept is None:
        	return ".html"
        for format in mappings:
            if format in accept:
                return mappings[format]
        return ".html"
        
    def write_error(self, status_code, **kwargs):
        """Attach human-readable msg to error messages"""
        self.error(status_code)
        self.response.out.write("Error %d - %s" % (status_code, kwargs['message']))

class HomeHandler(webapp2.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'static_files/ArtHistory.html')
        self.response.out.write(template.render(path, {}))

class AllPaintingsHandler(BaseHandler):
    SUPPORTED_METHODS = ("GET","POST")
    
    def get(self,format):
        paintings= self.db.list_paintings(self.base_uri)
        mappings= {".html":"text/html",".xml":"application/xml",".ttl":"text/turtle"}
        if format is None:
            fmt= self.get_format()
            self.redirect("/paintings"+fmt)
        elif format == ".json":
            self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
            self.response.out.write(json.dumps(paintings))
        elif format in mappings:
            content_type=mappings[format]
            self.response.headers.add_header("Content-Type", content_type)
            path = os.path.join(os.path.dirname(__file__), "static_files/paintings"+format)
            #logging.info("results " + str(paintings))
            values = {'paintings': paintings}
       	    self.response.out.write(template.render(path, values))
        else:
            self.write_error(401, message="Format %s not supported" % format)
            
    def post(self,format):
    	logging.info("results " + self.request.body)
        new_painting = json.loads(self.request.body)
        new_id = self.db.create_painting(new_painting[1])
        self.set_status(201)
        self.set_header("Location", self.base_uri + "/paintings/" + new_id)

class PaintingHandler(BaseHandler):
    SUPPORTED_METHODS = ("PUT", "GET", "DELETE")
    
    def get(self, paintingID, format):
        painting= self.db.get_painting(paintingID,self.base_uri)
        
        if painting is None:
            self.write_error(404, message="Painting %s does not exist" %paintingID)
        else:
            mappings= {".html":"text/html",".xml":"application/xml",".ttl":"text/turtle"}
            painting['success']=True
            
            try:
                 if urllib.urlopen(unicodedata.normalize('NFKD', painting['image'].decode('unicode-escape')).encode('ascii','ignore')).getcode() == 404:
                    painting['image'] = '../img/image_not_found.jpg'
            except UnicodeEncodeError:
            	painting['image'] = '../img/image_not_found.jpg'
            except IOError:
                pass
                   
            if format is None:
                fmt= self.get_format()
                self.redirect("/paintings/%s" %paintingID +fmt)
            elif format == ".json":
                self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
                self.response.out.write(painting)
            elif format in mappings:
                content_type=mappings[format]
                self.response.headers.add_header("Content-Type",content_type)
                path = os.path.join(os.path.dirname(__file__), "static_files/painting"+format)
       	        self.response.out.write(template.render(path, painting))
            else:
                self.write_error(401, message="Format %s not supported" % format)

    def put(self, paintingID, format):
        if paintingID in self.db.paintings:
            print "Updating painting %s" % paintingID
            new_painting = json.loads(self.request.body)
            self.db.update_painting(paintingID, new_painting[1])
        else:
            self.write_error(404,message="Painting %s does not exist" %paintingID)
            
    def delete(self, paintingID, format):
        if paintingID in self.db.paintings:
            print "Deleting painting %s" % paintingID
            self.db.delete_painting(paintingID)
        else:
            self.write_error(404, message="Painting %s does not exist" %paintingID)

class PointUpdateHandler(BaseHandler):
    def get(self, format):
    	responceDict = {'success':False, 'pieces':[], 'error':""}

        yearRange = self.request.get_all("yearRange[]")
        mediums = self.request.get_all("mediums[]")
        
        
        if yearRange is None or mediums is None:
            responceDict["error"] = "Incorrect GET arguments provided"
                
        else:
            """Need new set of points, their geocoordinates, painting ID, and possibly medium for
            map coloration purposes """
            
            pieces= self.db.filter(yearRange,mediums)
            
            if len(pieces) > 0:
                responceDict["pieces"] = pieces
                responceDict["success"] = True


        self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
        logging.info("results " + str(responceDict))
        self.response.out.write(json.dumps(responceDict))

class PaintingDatabase(object):
    """in memory database of MongoLab paintings database"""
    def __init__(self):
        #pull in full paintings collection from MongoLab
        self.apikey= "?apiKey=50c6ab59e4b05e32287d6e3d"
        self.fixedURL= "https://api.mongolab.com/api/1/databases/art_history/collections/paintings"
        url = self.fixedURL + self.apikey
        f= urllib.urlopen(url)
        paintings = f.read()
        f.close()
        results= json.loads(paintings)
        self.paintings={}
        self.mediums=[]
        for painting in results:
            painting['description']=cgi.escape(painting['description'],quote=True)
            self.paintings[painting["_id"]["$oid"]]=painting
            if "medium" in painting:
                if painting["medium"] not in self.mediums:
                    self.mediums.append(painting["medium"])
        
    # CRUD operations
    
    def list_paintings(self,base_uri):
        """Returns a list of all paintings"""
        paintings=[]
        for value in self.paintings.values():
            painting= dict(value)
            id= painting["_id"]
            uri= base_uri +"/paintings/"+str(id['$oid'])
            del painting["_id"]
            painting["uri"]=uri 
            paintings.append(painting)
        return paintings
    
    
    def get_painting(self, paintingID,base_uri):
        """Returns data about a painting"""
        if paintingID in self.paintings:
            painting= self.paintings[paintingID]
            uri= base_uri +"/paintings/"+str(paintingID)
            painting["uri"]=uri
            return painting
        else: 
            return None
    
    def update_painting(self, paintingID, painting):
        """Updates a painting with a given id"""
        self.paintings[paintingID] = painting
        
    def delete_painting(self, paintingID):
        """Deletes a painting"""
        del self.paintings[paintingID]

    def getAllTheLetters(begin='a', end='z'):
        beginNum = ord(begin)
        endNum = ord(end)
        for number in xrange(beginNum, endNum+1):
            yield chr(number)

    def getAllTheNumbers(begin='0', end='9'):
        beginNum = ord(begin)
        endNum = ord(end)
        for number in xrange(beginNum, endNum+1):
            yield chr(number)
        
    def create_painting(self, painting):
        """Creates a new painting and returns the assigned ID"""
        max_id = sorted([int(paintingID) for paintingID in self.paintings])[-1]
        new_id = str(max_id + 1)
        self.paintings[new_id] = painting
        return new_id

        
    # extra functions
        
    def filter(self,yearRange,mediums):
        """Returns paintings that fit the given yearRange and mediums"""
        results=[]
        
        validMediums = ["Oil painting", "Tempera on panel", "Oil and paper on canvas", "Fresco", "Acrylic paint", "Oil on canvas"]
        for painting in self.paintings.values():
            valid= True
            if "year_created" in painting:
                if int(painting["year_created"])> int(yearRange[1]) or int(painting["year_created"])< int(yearRange[0]):
                    valid= False
            if "medium" in painting and valid:
                    if mediums.__contains__('other') and not validMediums.__contains__(painting["medium"]):
                        valid=True
                    elif painting["medium"] not in mediums:
                        valid= False
                    
            if valid:

                results.append(painting)
        return results

db = PaintingDatabase()
                    
app = webapp2.WSGIApplication([ 
			#Default Home map
		    (r"/", HomeHandler),
		            
		    #Urls for REST retrieval of data
		    (r"/paintings(\..+)?", AllPaintingsHandler),
		    (r"/paintings/([0-9a-zA-Z]+)(\..+)?", PaintingHandler), 
		    (r"/paintings/([0-90-9a-zA-Z]+)/location(\..+)?", PaintingHandler),
		    
		    #Urls for Application's queries to the server
		    (r"/pointUpdate(\..+)?", PointUpdateHandler),
		    ],
		    debug=True)