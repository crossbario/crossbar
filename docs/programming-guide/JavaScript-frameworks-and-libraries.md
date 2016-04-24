We believe that browser frontends will increase in importance. Browsers are the most widely spread runtime ever, and they are gaining new features and capabilities at an amazing rate.

When developing application components for the browser, developers do (and should) take advantage of the rich ecosystem of libraries and development frameworks that exists. With new candidates constantly being released, and support for old ones ending, it's difficult to keep an overview.

This page aims to collect some of the more popular of these frameworks, and give an idea of whether they can be a useful part of developing Crossbar.io applications. If so, then this also collects links to resources to help get you started.

**This is very much a work in progress, and contributions are highly welcome!**

## Frameworks

### Angular

- write me -

**Learn more:**

- The [AngularJS website](https://angularjs.org/) offers a lot of information, including tutorials.
- There's an [[introduction to combining Crossbar and AngularJS | AngularJS-Application-Components]] in this wiki

### Ember

[Ember.js](http://emberjs.com/) is a frontend framework which provides routing, templating and data binding. 

- write me -

notes:
- data binding
- components (using Handelbars)
- routing & url handling

### Dojo

[Dojo](http://dojotoolkit.org/)

### Backbone

[Backbone.js](http://documentcloud.github.io/backbone/)


### Polymer

[Polymer](http://www.polymer-project.org/) is a framework by Google which is based on elements. Functionality is packaged into them (using the new Web Components technologies), so they can be used easily in your markup - just like existing HTML elements. Elements can also be combined to form new elements, allowing to build complex functionality from simpler blocks. It provides a large number of elements and allows you to create your own elements. Since Polymer uses the most current Web technologies, it also provides polyfills for missing APIs.

Since Polymer focuses on elements, it is easy to combine with other libraries or frameworks. While we have no experience with Polymer and Crossbar.io, there are no obvious showstoppers here in combining the two.

### Kendo

[Kendo UI](http://www.telerik.com/kendo-ui)

### Meteor

[Meteor](https://www.meteor.com/) is a full-stack JavaScript only framework - it covers both the frontend and the backend. As such it provides its own mechanisms for communication between the browser and Node.js, including real-time updates. While it would certainly be possible to replace parts of Meteor to use Crossbar.io, it is doubtful whether would be worth the effort. You would gain capabilities, but lose out on the integration.


## Libraries

### Knockout

[KnockoutJS](http://knockoutjs.com/) is a library for MVVM applications. It provides a lot of features for user interfaces, such as two-way data binding for UI elements, adding markup based on array contents and templating. The newest version has added a component system as well. Knockout extends beyond UIs, though: 'computeds' are values which are dynamically updated if any dependent variables change. Using this and subscriptions to variables, you can build applications where data changes automatically trigger actions, and reduce coupling in your code.

While Knockout offers powerful features, it is a library. You can use it as much or as little as you want in your projects, so it's easy to dip your feet in a little first, and to combine it with other libraries.

We have been using KnockoutJS for our own applications for a while now, and find it combines very well with Crossbar.io. The two-way data binding is perfect for real-time updates.

**Learn more:**

- The [tutorials on the Knockout homepage](http://learn.knockoutjs.com/) are a great place to start learning knockout concepts.
- the Crossbar Editform demo has a Knockout variant (but beware, the code needs refactoring). A tutorial for this should be up shortly


## UI frameworks

### Bootstrap

At its most basic Bootstrap provides CSS styles for your page, but you can also use some provided widgets, such as the seemingly ubiquitous responsive top navigation. In our limited use so far, any problems we've encountered have been with the framework itself, not with the combination with Crossbar.

### jQuery Mobile

jQuery mobile provides both UI elements and app routing, with a focus on cross-device deployment. Our experience with this and Crossbar is purely in the combination of jQuery mobile + Knockout.JS - and that was a pain. Otherwise it should be easy enough to combine.

### React

[React](http://facebook.github.io/react/)
